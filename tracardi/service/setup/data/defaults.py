import os

from tracardi.service.utils.date import now_in_utc
from tracardi.service.plugin.domain.register import Form, FormGroup, FormField, FormComponent
from tracardi.config import tracardi
from tracardi.domain.bridge import Bridge
from tracardi.domain.event_source import EventSource
from tracardi.domain.named_entity import NamedEntity

_local_dir = os.path.dirname(__file__)

open_rest_source_bridge = Bridge(
    id="778ded05-4ff3-4e08-9a86-72c0195fa95d",
    type="rest",
    name="REST API Bridge",
    description="API /track collector",
    config={
        "static_profile_id": False
    },
    form=Form(groups=[
        FormGroup(
            name="REST API Bridge Configuration",
            fields=[
                FormField(
                    id="static_profile_id",
                    name="Allow static profile ID.",
                    description="This feature allows you to use profile IDs that were not generated by Tracardi. "
                                "The delivered profile ID will be used to create a non-existing profile ID. However, "
                                "please note that using this feature can pose a security risk. It's important to read "
                                "Tracardi documentation carefully before using it.",
                    component=FormComponent(type="bool", props={"label": "Allow static, remotely defined profile ID"})
                )
            ])
    ])
)

open_webhook_source_bridge = Bridge(
    id="3d8bb87e-28d1-4a38-b19c-d0c1fbb71e22",
    type="webhook",
    name="API Webhook Bridge",
    description="API Webhook collector",
    config={
        "generate_profile": False,
        "replace_profile_id": "",
        "replace_session_id": "",
        "identify_profile_by": None
    },
    form=Form(groups=[
        FormGroup(
            name="API Webhook Bridge Configuration",
            description="The webhook bridge usually collects data without connection to a profile or session. "
                        "But, if you need to make a profile and session for the data it collects, and you want "
                        "to make sure that it matches an existing profile, you should set up matching details below.",
            fields=[
                FormField(
                    id="generate_profile",
                    name="Create profile and session for collected data.",
                    description="By default, webhook events do not include session or profile IDs. "
                                "However, if you enable this settings, it will generate the profile and session "
                                "ID for this event.",

                    component=FormComponent(type="bool", props={"label": "Create profile and session"})
                )
            ]),
        FormGroup(
            name="Use Auto Profile Merging",
            fields=[
                FormField(
                    id="identify_profile_by",
                    name="Identification method",
                    description="Select the method to identify the profile. If 'e-mail' or 'phone' is "
                                "chosen, a Profile will be identified by the 'e-mail' or 'phone'. "
                                "The exact location of the data should be defined in 'Set Profile ID from Payload' field. "
                                "Selecting 'nothing' means no Profile ID will be matched. If 'custom ID' is "
                                "selected, the Profile ID will be the same as the payload value referenced in "
                                "the 'Set Profile ID from Payload' field.",
                    component=FormComponent(
                        type="select",
                        props={
                            "label": "Profile identified by",
                            "items": {
                                "none": "No Reference",
                                "e-mail": 'Main E-Mail',
                                "phone": "Main Phone",
                                "id": "Custom ID"
                            }
                        }
                    )
                ),
                FormField(
                    id="replace_profile_id",
                    name="Set Profile ID from Payload",
                    description="To set the Profile ID, type the location of Profile ID Identifier in payload below or leave "
                                "the field blank if you don't wish "
                                "to set any profile or want it to have a random ID. "
                                "If 'Custom ID' is chosen as identification method, then enter the location where the Profile ID "
                                "is stored in payload the; ID will be used as is without modification. "
                                "For 'e-mail' or 'phone' options,  enter the location where e-mail or phone is stored; "
                                "the system automatically generates a secure, hash-based Profile ID from the data in "
                                "the payload. It will automatically load profile for the e-mail of phone defined "
                                "in payload. "
                                "This setting will only work when `Create session and profile` is enabled. ",
                    component=FormComponent(type="text", props={"label": "Reference to Profile ID in webhook payload"})
                ),
                FormField(
                    id="replace_session_id",
                    name="Set Session ID from Payload",
                    description="This setting will only work when `Create session and profile` is enabled. "
                                "If you intend to substitute or set the Session ID with information from the payload, "
                                "you can either use the data provided below or leave it blank if you don't wish "
                                "to set any session or want it to have a random ID. It is crucial to ensure "
                                "that the Session ID is secure and not easily predictable since simple Session "
                                "IDs may pose security threats.",
                    component=FormComponent(type="text", props={"label": "Reference to Session ID in webhook payload"})
                )
            ])
    ])
)

with open(os.path.join(_local_dir, "manual/redirect_manual.md"), "r", encoding="utf-8") as fh:
    manual = fh.read()

redirect_bridge = Bridge(
    id='a495159f-91be-476d-a4e5-1b2d7e005403',
    type='redirect',
    name="Redirect URL Bridge",
    description="Redirects URLs and registers events.",
    manual=manual
)

# This is how you set-up default event source
test_event_source = EventSource(
    id=tracardi.demo_source,
    type=["rest"],
    name="System Test Source",
    channel="Test",
    description="This is test event-source. Feel free to remove it.",
    bridge=NamedEntity(**open_rest_source_bridge.model_dump()),
    timestamp=now_in_utc(),
    tags=["test"],
    groups=["Test"]
)

default_db_data = {
    "bridge": [
        open_rest_source_bridge.model_dump(mode='json'),
        open_webhook_source_bridge.model_dump(mode='json'),
        redirect_bridge.model_dump(mode='json')
    ],
    'event-source': [
        test_event_source.model_dump(mode='json')
    ]
}
