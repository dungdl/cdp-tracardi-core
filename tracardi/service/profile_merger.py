import logging
from ..service.storage.driver import storage
from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from pydantic.utils import deep_update, KeyType

from ..config import tracardi
from ..domain.metadata import ProfileMetadata
from ..domain.profile import Profile
from ..domain.profile_stats import ProfileStats
from ..domain.time import ProfileTime
from ..exceptions.log_handler import log_handler
from ..service.dot_notation_converter import DotNotationConverter

from tracardi.service.merger import merge as dict_merge, get_changed_values

logger = logging.getLogger(__name__)
logger.setLevel(tracardi.logging_level)
logger.addHandler(log_handler)


class ProfileMerger:

    def __init__(self, profile: Profile, allow_merge_by_id=False):
        self.allow_merge_by_id = allow_merge_by_id
        self.current_profile = profile

    @staticmethod
    async def _delete_duplicate_profiles(duplicate_profiles: List[Profile]):
        profile_by_index: Dict[str, List[Profile]] = defaultdict(list)
        for dup_profile in duplicate_profiles:
            profile_by_index[dup_profile.get_meta_data().index].append(dup_profile)

        # Iterate one by one
        # Todo maybe some bulk delete
        for _, dup_profile_bulk in profile_by_index.items():
            for dup_profile in dup_profile_bulk:
                await storage.driver.profile.delete_by_id(dup_profile.id, dup_profile.get_meta_data().index)

    @staticmethod
    async def _save_mark_duplicates_as_inactive_profiles(duplicate_profiles: List[Profile]):
        profile_by_index = defaultdict(list)
        for dup_profile in duplicate_profiles:
            profile_by_index[dup_profile.get_meta_data().index].append(dup_profile)

        for _, dup_profile_bulk in profile_by_index.items():
            await storage.driver.profile.save_all(dup_profile_bulk)

    @staticmethod
    async def _copy_duplicated_profiles_ids_to_merged_profile_ids(merged_profile: Profile,
                                                                  duplicate_profiles: List[Profile]) -> Profile:
        merged_profile.ids.append(merged_profile.id)

        for dup_profile in duplicate_profiles:
            if isinstance(dup_profile.ids, list):
                merged_profile.ids += dup_profile.ids
        merged_profile.ids = list(set(merged_profile.ids))

        return merged_profile

    @staticmethod
    async def _save_profile(profile):
        await storage.driver.profile.save(profile, refresh_after_save=False)
        await storage.driver.profile.refresh()

    @staticmethod
    async def _delete_profile(profile_ids):
        return await storage.driver.profile.bulk_delete_by_id(ids=profile_ids)

    @staticmethod
    async def _move_profile_events_and_sessions(duplicate_profiles: List[Profile], merged_profile: Profile):
        for old_profile in duplicate_profiles:
            if old_profile.id != merged_profile.id:
                await storage.driver.raw.update_profile_ids('event', old_profile.id, merged_profile.id)
                await storage.driver.event.refresh()
                await storage.driver.raw.update_profile_ids('session', old_profile.id, merged_profile.id)
                await storage.driver.session.refresh()

    @staticmethod
    async def invoke_merge_profile(profile: Optional[Profile],
                                   merge_by: List[Tuple[str, str]],  # Field: value
                                   conflict_aux_key: str = "conflicts",
                                   allow_merge_by_id=False,
                                   limit: int = 2000) -> Optional[Profile]:
        if len(merge_by) > 0:
            # Load all profiles that match merging criteria
            logger.info("Loading profiles to merge")
            similar_profiles = await storage.driver.profile.load_profiles_to_merge(
                merge_by,
                limit=limit
            )

            if len(similar_profiles) == 0:
                logger.info("No similar profiles to merge")
                return None

            merger = ProfileMerger(profile, allow_merge_by_id)

            # Merge
            merged_profile, duplicate_profiles = await merger.merge(
                similar_profiles,
                conflict_aux_key=conflict_aux_key)

            if merged_profile:
                # Copy ids
                merged_profile = await ProfileMerger._copy_duplicated_profiles_ids_to_merged_profile_ids(
                    merged_profile,
                    duplicate_profiles)

                await ProfileMerger._save_profile(merged_profile)

                # Schedule - move events from duplicated profiles
                await ProfileMerger._move_profile_events_and_sessions(duplicate_profiles, merged_profile)

                # Schedule - mark duplicated profiles
                # await ProfileMerger._save_mark_duplicates_as_inactive_profiles(duplicate_profiles)
                records_to_delete = [profile.id for profile in duplicate_profiles]
                await ProfileMerger._delete_profile(records_to_delete)

                # Replace current profile with merged profile
                profile.replace(merged_profile)

                return profile

            else:
                logger.info("No need to merge")

        return None

    @staticmethod
    async def invoke_deduplicate_profile(profile: Optional[Profile],
                                         merge_by: List[Tuple[str, str]],
                                         limit: int = 2000) -> Optional[Profile]:
        if len(merge_by) > 0:
            # Load all profiles that match merging criteria
            similar_profiles = await storage.driver.profile.load_profiles_to_merge(
                merge_by,
                limit=limit
            )

            merger = ProfileMerger(profile)

            # Merge
            merged_profile, profiles_to_delete = await merger.deduplicate(
                similar_profiles)

            if merged_profile:
                # Remove duplicated profiles

                await ProfileMerger._delete_duplicate_profiles(profiles_to_delete)

                # Replace current profile with merged profile
                profile.replace(merged_profile)

                # Update profile after merge
                profile.operation.update = True

                return profile

        return None

    @staticmethod
    def _get_merge_key_values(profile: Profile) -> List[tuple]:
        converter = DotNotationConverter(profile)
        values = [converter.get_profile_file_value_pair(key) for key in profile.operation.merge]
        return values

    @staticmethod
    def get_merging_keys_and_values(profile: Profile) -> List[Tuple[str, str]]:
        merge_key_values = ProfileMerger._get_merge_key_values(profile)

        # Add keyword
        merge_key_values = [(field, value) for field, value in merge_key_values if value is not None]

        return merge_key_values

    @staticmethod
    def _mark_profiles_as_merged(profiles: List[Profile], merge_with: str) -> List[Profile]:
        disabled_profiles = []

        for profile in profiles:
            profile.active = False
            profile.metadata.merged_with = merge_with
            disabled_profiles.append(profile)

        return disabled_profiles

    @staticmethod
    def _deep_update(mapping: Dict[KeyType, Any], *updating_mappings: Dict[KeyType, Any]) -> Dict[KeyType, Any]:
        updated_mapping = mapping.copy()
        for updating_mapping in updating_mappings:
            for k, v in updating_mapping.items():
                if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                    updated_mapping[k] = deep_update(updated_mapping[k], v)
                elif v is not None:
                    updated_mapping[k] = v
        return updated_mapping

    def _get_merged_profile(self,
                            similar_profiles: List[Profile],
                            conflict_aux_key: str = "conflicts",
                            merge_stats: bool = True,
                            merge_time: bool = True
                            ) -> Profile:

        all_profiles = similar_profiles + [self.current_profile]

        # Merge traits and piis

        """
           Marge do not loose data. Conflicts are resoled to list of values.
           E.g. Name="bill" + Name="Wiliam"  = Name=['bill','wiliam']
        """

        _traits = [profile.traits.dict() for profile in all_profiles]
        _piis = [profile.pii.dict() for profile in all_profiles]

        old_value = {
            'traits': _traits,
            'piis': _piis
        }

        new_value = {
            'traits': dict_merge({}, _traits),
            'piis': dict_merge({}, _piis)
        }

        conflicts_aux = get_changed_values(old_value, new_value)

        """
            Marge overrides data. Conflicts are resoled to single value. Latest wins.
            E.g. Name="bill" + Name="Wiliam" = Name='wiliam'
        """

        current_profile_dict = self.current_profile.dict()

        for profile in all_profiles:
            current_profile_dict['traits'] = self._deep_update(current_profile_dict['traits'],
                                                               profile.traits.dict())
            current_profile_dict['pii'] = self._deep_update(current_profile_dict['pii'], profile.pii.dict())

        traits = current_profile_dict['traits']
        piis = current_profile_dict['pii']

        # Merge stats, consents, segments, etc.

        consents = {}
        segments = []
        interests = {}
        stats = ProfileStats()
        time = ProfileTime(**self.current_profile.metadata.time.dict())
        time.visit.count = 0  # Reset counter - it sums all the visits

        for profile in all_profiles:  # Type: Profile

            # Time
            if merge_time:
                time.visit.count += profile.metadata.time.visit.count

                if isinstance(time.insert, datetime) and isinstance(profile.metadata.time.insert, datetime):
                    # Get earlier date
                    if time.insert > profile.metadata.time.insert:
                        time.insert = profile.metadata.time.insert

                if isinstance(time.visit.current, datetime) and isinstance(profile.metadata.time.visit.current,
                                                                           datetime):
                    if time.visit.current < profile.metadata.time.visit.current:
                        time.visit.current = profile.metadata.time.visit.current

                if isinstance(time.visit.last, datetime) and isinstance(profile.metadata.time.visit.last, datetime):
                    if time.visit.last < profile.metadata.time.visit.last:
                        time.visit.last = profile.metadata.time.visit.last

            # Stats

            if merge_stats:
                stats.visits += profile.stats.visits
                stats.views += profile.stats.views

                for key, value in profile.stats.counters.items():
                    if key not in stats.counters:
                        stats.counters[key] = 0
                    stats.counters[key] += value

            # Segments

            if isinstance(profile.segments, list):
                segments += profile.segments
                segments = list(set(segments))

            # Consents

            consents.update(profile.consents)

            # Interests

            for interest, count in profile.interests.items():
                if interest not in interests:
                    interests[interest] = 0
                interests[interest] += profile.interests[interest]

        # Set id to merged id or current profile id.
        id = self.current_profile.metadata.merged_with if self.current_profile.metadata.merged_with is not None else self.current_profile.id

        self.current_profile.aux[conflict_aux_key] = conflicts_aux

        profile = Profile(
            metadata=ProfileMetadata(time=time),
            id=id,
            ids=self.current_profile.ids,
            stats=stats if merge_stats else self.current_profile.stats,
            traits=traits,
            pii=piis,
            segments=segments,
            consents=consents,
            interests=dict(interests),
            active=True,
            aux=self.current_profile.aux
        )

        profile.set_meta_data(self.current_profile.get_meta_data())

        return profile

    async def merge(self,
                    similar_profiles: List[Profile],
                    conflict_aux_key: str = "conflicts") -> Tuple[Optional[Profile], List[Profile]]:
        """
        Merges profiles on keys set in profile.operation.merge. Loads profiles from database and
        combines its data into current profile. Returns Profiles object with profiles to be disables.
        It does not disable profiles or saves merged profile.
        """

        merged_profile = None
        disabled_profiles = []

        if len(similar_profiles) > 0:

            # Filter only profiles that are not current profile and where not merged
            if self.allow_merge_by_id is True:
                profiles_to_merge = [p for p in similar_profiles if p.active is True]
            else:
                profiles_to_merge = [p for p in similar_profiles if p.id != self.current_profile.id and p.active is True]

            # Are there any profiles to merge?
            if len(profiles_to_merge) > 0:
                # Add current profile to existing ones and get merged profile

                merged_profile = self._get_merged_profile(
                    profiles_to_merge,
                    conflict_aux_key=conflict_aux_key)

                # Deactivate all other profiles except merged one

                # todo On id then strange

                profiles_to_disable = [p for p in similar_profiles if p.id != self.current_profile.id]
                disabled_profiles = self._mark_profiles_as_merged(profiles_to_disable,
                                                                  merge_with=self.current_profile.id)

        return merged_profile, disabled_profiles

    async def deduplicate(self,
                          similar_profiles: List[Profile]) -> Tuple[Optional[Profile], List[Profile]]:

        merged_profile = None
        profiles_to_delete = []
        if len(similar_profiles) > 1:
            # Add current profile to existing ones and get merged profile

            merged_profile = self._get_merged_profile(
                similar_profiles,
                merge_stats=False,
                merge_time=True
            )

            # Get Profiles to delete

            # Deactivate all other profiles except merged one

            profiles_to_delete = [p for p in similar_profiles
                                  if p.get_meta_data().index != self.current_profile.get_meta_data().index]

        return merged_profile, profiles_to_delete
