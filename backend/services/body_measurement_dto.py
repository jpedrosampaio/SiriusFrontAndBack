from datetime import date as Date
from pydantic import BaseModel,Field


class MeasurementBody(BaseModel):
    date: Date
    weight_kg: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    body_fat_percentage: float | None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    muscle_mass_kg: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    bone_mass_kg: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    water_percentage: float | None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    visceral_fat: int | None=Field(default=None,ge=0)
    metabolic_age: int | None=Field(default=None,ge=0)
    bmr_kcal: int | None=Field(default=None,ge=0)
    height_cm: float | None=Field(default=None,gt=0,allow_inf_nan=False)
    neck_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    shoulders_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    chest_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    waist_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    abdomen_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    hips_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    left_arm_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    right_arm_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    left_forearm_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    right_forearm_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    left_thigh_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    right_thigh_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    left_calf_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    right_calf_cm: float | None=Field(default=None,ge=0,allow_inf_nan=False)
    notes: str | None=Field(default=None,max_length=20000)
    source: str=Field(default='manual',max_length=100)
