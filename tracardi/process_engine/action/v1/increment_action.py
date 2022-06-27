from typing import Union

from pydantic import validator
from tracardi.service.plugin.domain.register import Plugin, Spec, MetaData, Form, FormGroup, FormField, FormComponent, \
    Documentation, PortDoc
from tracardi.service.plugin.runner import ActionRunner
from tracardi.service.plugin.domain.result import Result
from tracardi.domain.profile import Profile
from tracardi.service.plugin.domain.config import PluginConfig


class IncrementConfig(PluginConfig):
    field: str
    increment: Union[int, float]

    @validator('field')
    def field_must_match(cls, value):
        if not value.startswith('profile@stats.counters'):
            raise ValueError(f"Only fields inside `profile@stats.counters` can be incremented. Field `{value}` given.")
        return value


def validate(config: dict):
    return IncrementConfig(**config)


class IncrementAction(ActionRunner):

    def __init__(self, **kwargs):
        self.config = validate(kwargs)

    async def run(self, payload):

        dot = self._get_dot_accessor(payload if isinstance(payload, dict) else None)

        try:

            value = dot[self.config.field]

            if value is None:
                value = 0

        except KeyError:
            value = 0

        if type(value) != int:
            raise ValueError("Filed `{}` value is not numeric.".format(self.config.field))

        value += self.config.increment

        dot[self.config.field] = value

        if self.event.metadata.profile_less is False:
            self.profile.replace(Profile(**dot.profile))

        return Result(port="payload", value=payload)


def register() -> Plugin:
    return Plugin(
        start=False,
        spec=Spec(
            module='tracardi.process_engine.action.v1.increment_action',
            className='IncrementAction',
            inputs=["payload"],
            outputs=['payload'],
            init={"field": "", "increment": 1},
            form=Form(groups=[
                FormGroup(
                    fields=[
                        FormField(
                            id="field",
                            name="Path to field",
                            description="Provide path to field that should be incremented. "
                                        "E.g. profile@stats.counters.boughtProducts",
                            component=FormComponent(type="dotPath", props={"label": "Field path"})
                        )
                    ]
                ),
                FormGroup(
                    fields=[
                        FormField(
                            id="increment",
                            name="Incrementation",
                            description="Provide by what number the value at provided path should "
                                        "be incremented. Default value equals 1.",
                            component=FormComponent(
                                type="text",
                                props={
                                    "label": "Incrementation"
                                })
                        )
                    ]

                ),
            ]),
            manual="increment_action",
            version='0.1',
            license="MIT",
            author="Risto Kowaczewski"
        ),
        metadata=MetaData(
            name='Increment counter',
            desc='Increments given field in payload, returns payload.',
            icon='plus',
            group=["Stats"],
            documentation=Documentation(
                inputs={
                    "payload": PortDoc(desc="This port takes any JSON-like object.")
                },
                outputs={
                    "payload": PortDoc(desc="This port returns object received by plugin in input.")
                }
            )
        )
    )
