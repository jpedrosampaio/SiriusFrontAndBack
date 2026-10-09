from datetime import date
from typing import Literal
from pydantic import BaseModel,Field,AliasChoices,field_validator,model_validator
from services.nutrition import Nonnegative
from services.recipe_routes import IngredientBody

class GenerationOptions(BaseModel):
    objective: str=Field(default='saude',max_length=1000)
    restrictions: list[str]=Field(default_factory=list,max_length=100)
    meals_per_day: int=Field(default=5,ge=1,le=20,strict=True)
    duration: Literal['dia','semana']='dia'
    calories_target: Nonnegative=0

class PlannedFoodBody(IngredientBody):
    calories: Nonnegative=0
    protein: Nonnegative=0
    carbs: Nonnegative=0
    fat: Nonnegative=0
    known_macros: list[Literal['calories','protein','carbs','fat']] | None=Field(default=None,max_length=4)
    @model_validator(mode='before')
    @classmethod
    def supplied_macros(cls,data):
        if isinstance(data,dict) and data.get('known_macros') is None:
            return {**data,'known_macros':[key for key in ('calories','protein','carbs','fat') if key in data]}
        return data

class PlannedMealBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    meal_type: str=Field(default='snack',max_length=100)
    time: str=Field(default='',max_length=20)
    preparation: str=Field(default='',max_length=20000)
    notes: str=Field(default='',max_length=20000)
    calories: Nonnegative=Field(default=0,validation_alias=AliasChoices('calories','total_calories'))
    protein: Nonnegative=0
    carbs: Nonnegative=0
    fat: Nonnegative=0
    fiber: Nonnegative=0
    foods: list[PlannedFoodBody]=Field(default_factory=list,max_length=100)
    @model_validator(mode='before')
    @classmethod
    def derive_missing(cls,data):
        if isinstance(data,dict):
            data=dict(data)
            for key in ('calories','protein','carbs','fat'):
                if key not in data and not (key=='calories' and 'total_calories' in data):
                    try:data[key]=sum(float(food.get(key,0)) for food in data.get('foods',[]) if isinstance(food,dict))
                    except (ValueError,TypeError):pass
        return data

class DayBody(BaseModel):
    day_name: str=Field(default='dia1',max_length=100)
    day_label: str=Field(default='',max_length=100)
    calories: Nonnegative=0
    meals: list[PlannedMealBody]=Field(min_length=1,max_length=20)

class ShoppingEntry(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    quantity: str=Field(default='',max_length=1000)
    category: str=Field(default='outros',max_length=100)
    @field_validator('quantity',mode='before')
    @classmethod
    def quantity_text(cls,value):return str(value) if isinstance(value,(int,float)) else value

class PlanBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    description: str | None=Field(default=None,max_length=20000)
    objective: str=Field(default='',max_length=2000)
    diet_type: str=Field(default='',max_length=100)
    start_date: date | None=None
    end_date: date | None=None
    source_filename: str | None=None
    daily_calories: Nonnegative=0
    daily_protein: Nonnegative=0
    daily_carbs: Nonnegative=0
    daily_fat: Nonnegative=0
    daily_fiber: Nonnegative=0
    restrictions: list[str]=Field(default_factory=list,max_length=100)
    tips: list[str]=Field(default_factory=list,max_length=100)
    days: list[DayBody]=Field(default_factory=list,max_length=31)
    shopping_items: list[ShoppingEntry]=Field(default_factory=list,max_length=1000)
    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date and self.end_date and self.end_date<self.start_date:raise ValueError('Invalid date range')
        return self

class DietBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    description: str | None=Field(default=None,max_length=20000)
    diet_type: str=Field(max_length=100)
    meals_plan: list[PlannedMealBody]=Field(default_factory=list,max_length=20)
    start_date: date
    end_date: date | None=None
    @model_validator(mode='after')
    def valid_dates(self):
        if self.end_date and self.end_date<self.start_date:raise ValueError('Invalid date range')
        return self

class ConfirmPlan(BaseModel):
    preview_id: str=Field(pattern=r'^nutrition-preview-[a-f0-9]{32}$')
    plan: PlanBody
