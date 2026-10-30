from typing import Literal

from pydantic import BaseModel

Source = Literal["page", "ai"]


class Field(BaseModel):
    value: str
    source: Source


class LabeledField(BaseModel):
    label: str
    value: str
    source: Source


class ReactionRecord(BaseModel):
    mode: Literal["notebook", "prediction"]
    equation: Field
    reactants: list[Field]
    products: list[LabeledField]
    conditions: list[LabeledField]
    procedure: Field
    outcome: list[LabeledField]
