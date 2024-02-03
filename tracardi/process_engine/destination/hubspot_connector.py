from hashlib import sha1

from .destination_interface import DestinationInterface
from ..action.v1.connectors.hubspot.client import HubSpotClient, HubSpotClientException
from ...domain.event import Event
from ...domain.profile import Profile
from ...domain.session import Session


class HubSpotConnector(DestinationInterface):

    name = 'hubspot'

    @staticmethod
    def _get_hash_of_values(data):
        return sha1(f"{data['firstname']}-{data['lastname']}-{data['email']}".encode()).hexdigest()

    async def _dispatch(self, data, profile: Profile):

        credentials = self._get_credentials()
        client = HubSpotClient(credentials.get('token', None))

        if profile.data.pii.firstname:
            data["firstname"] = profile.data.pii.firstname
        if profile.data.pii.firstname:
            data["lastname"] = profile.data.pii.lastname
        if profile.data.contact.email.main:
            data["email"] = profile.data.contact.email.main

        # If there is any data to send

        if data:

            new_hash = self._get_hash_of_values(data)

            if profile.metadata.system.has_integration(self.name):
                integration = profile.metadata.system.get_integration(self.name)

                old_hash = integration.data.get('hash', None)

                # If data changed
                if old_hash != new_hash:
                    await client.update_contact(integration.id, data)

                    # Update hash
                    profile.metadata.system.set_integration(self.name, integration.id, {"hash": new_hash})
                    profile.mark_for_update()

            else:
                try:
                    response = await client.add_contact(data)
                    if 'id' in response:
                        profile.metadata.system.set_integration(self.name, response['id'], {"hash": new_hash})
                        profile.mark_for_update()
                except HubSpotClientException:
                    if 'email' in data:
                        ids = await client.get_contact_ids_by_email(data["email"])
                        if len(ids) > 0:
                            profile.metadata.system.set_integration(self.name, ids[0], {"hash": new_hash})
                            profile.mark_for_update()
    async def dispatch_profile(self, data, profile: Profile, session: Session):
        await self._dispatch(data, profile)

    async def dispatch_event(self, data, profile: Profile, session: Session, event: Event):
        await self._dispatch(data, profile)