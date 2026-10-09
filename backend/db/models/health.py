from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class WorkoutPlan(Identity, Owned, Timestamps, Base):
    __tablename__ = 'workout_plans'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    plan_duration: Mapped[str] = mapped_column(default='dia')
    objective: Mapped[str | None]
    level: Mapped[str | None]
    generated_by_ai: Mapped[bool] = mapped_column(default=False)
    generation_parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    improved_from: Mapped[UUID | None]
    improvements_summary: Mapped[str | None] = mapped_column(Text)
    days: Mapped[list['WorkoutDay']] = relationship(back_populates='plan', passive_deletes=True, order_by='WorkoutDay.position')
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','improved_from'],['workout_plans.user_id','workout_plans.id'],ondelete='RESTRICT'))


class WorkoutDay(Identity, Owned, Base):
    __tablename__ = 'workout_plan_days'
    plan_id: Mapped[UUID]
    position: Mapped[int]
    week: Mapped[int]
    label: Mapped[str]
    name: Mapped[str]
    split_label: Mapped[str] = mapped_column(default='')
    progression_focus: Mapped[str] = mapped_column(default='')
    progression_notes: Mapped[str] = mapped_column(Text,default='')
    plan: Mapped[WorkoutPlan] = relationship(back_populates='days')
    exercises: Mapped[list['PlanExercise']] = relationship(back_populates='day',passive_deletes=True,order_by='PlanExercise.position')
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','plan_id','position'),
        ForeignKeyConstraint(['user_id','plan_id'],['workout_plans.user_id','workout_plans.id'],ondelete='CASCADE'),
        CheckConstraint('week >= 1 AND position >= 0',name='position'))


class ExerciseFields:
    name: Mapped[str]
    position: Mapped[int]
    sets: Mapped[int]
    reps: Mapped[str]
    weight: Mapped[str] = mapped_column(default='')
    rest_seconds: Mapped[int] = mapped_column(default=60)
    muscle_group: Mapped[str] = mapped_column(default='')
    tutorial: Mapped[str] = mapped_column(Text,default='')
    video_url: Mapped[str] = mapped_column(Text,default='')
    notes: Mapped[str] = mapped_column(Text,default='')


class PlanExercise(Identity, Owned, ExerciseFields, Base):
    __tablename__ = 'plan_exercises'
    day_id: Mapped[UUID]
    day: Mapped[WorkoutDay] = relationship(back_populates='exercises')
    __table_args__ = (UniqueConstraint('user_id','day_id','position'),
        ForeignKeyConstraint(['user_id','day_id'],['workout_plan_days.user_id','workout_plan_days.id'],ondelete='CASCADE'),
        CheckConstraint('sets > 0 AND rest_seconds >= 0',name='sets_rest'))


class WorkoutSession(Identity, Owned, Base):
    __tablename__ = 'workout_sessions'
    plan_id: Mapped[UUID]
    plan_name: Mapped[str]
    day_index: Mapped[int]
    status: Mapped[str] = mapped_column(default='active')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_duration_seconds: Mapped[int] = mapped_column(default=0)
    current_exercise_idx: Mapped[int] = mapped_column(default=0)
    rest_timer_seconds: Mapped[int] = mapped_column(default=60)
    revision: Mapped[int] = mapped_column(default=0)
    feedback: Mapped[dict | None] = mapped_column(JSONB)
    exercises: Mapped[list['SessionExercise']] = relationship(back_populates='session',passive_deletes=True,order_by='SessionExercise.position')
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','plan_id'],['workout_plans.user_id','workout_plans.id'],ondelete='RESTRICT'),
        CheckConstraint("status IN ('active','completed','abandoned')",name='status'),
        Index('uq_workout_active_user','user_id',unique=True,postgresql_where=status == 'active'),
        CheckConstraint('total_duration_seconds >= 0',name='duration'))


class SessionExercise(Identity, Owned, ExerciseFields, Base):
    __tablename__ = 'session_exercises'
    session_id: Mapped[UUID]
    completed: Mapped[bool] = mapped_column(default=False)
    sets_completed: Mapped[int] = mapped_column(default=0)
    time_spent_seconds: Mapped[int] = mapped_column(default=0)
    session: Mapped[WorkoutSession] = relationship(back_populates='exercises')
    actual_sets: Mapped[list['WorkoutSet']] = relationship(back_populates='exercise',passive_deletes=True,order_by='WorkoutSet.position')
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','session_id','position'),
        ForeignKeyConstraint(['user_id','session_id'],['workout_sessions.user_id','workout_sessions.id'],ondelete='RESTRICT'),
        CheckConstraint('sets_completed BETWEEN 0 AND sets AND time_spent_seconds >= 0',name='completion'))


class WorkoutSet(Identity, Owned, Base):
    __tablename__ = 'workout_sets'
    exercise_id: Mapped[UUID | None]
    log_exercise_id: Mapped[UUID | None]
    position: Mapped[int]
    reps: Mapped[int | None]
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10,3))
    rpe: Mapped[float | None]
    completed: Mapped[bool] = mapped_column(default=False)
    exercise: Mapped[SessionExercise] = relationship(back_populates='actual_sets')
    __table_args__ = (UniqueConstraint('user_id','exercise_id','position'),
        UniqueConstraint('user_id','log_exercise_id','position'),
        ForeignKeyConstraint(['user_id','log_exercise_id'],['workout_log_exercises.user_id','workout_log_exercises.id'],ondelete='CASCADE'),
        CheckConstraint('(exercise_id IS NOT NULL)::integer + (log_exercise_id IS NOT NULL)::integer = 1',name='one_exercise_source'),
        ForeignKeyConstraint(['user_id','exercise_id'],['session_exercises.user_id','session_exercises.id'],ondelete='RESTRICT'),
        CheckConstraint('reps IS NULL OR reps >= 0',name='reps'),CheckConstraint('rpe IS NULL OR rpe BETWEEN 0 AND 10',name='rpe'))


class WorkoutLog(Identity, Owned, Timestamps, Base):
    __tablename__ = 'workout_logs'
    session_id: Mapped[UUID | None]
    plan_id: Mapped[UUID | None]
    activity_type: Mapped[str]
    name: Mapped[str]
    duration_minutes: Mapped[int]
    distance_km: Mapped[float | None]
    calories: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    xp_earned: Mapped[int] = mapped_column(default=0)
    completed: Mapped[bool] = mapped_column(default=True)
    date: Mapped[date] = mapped_column(Date)
    exercises: Mapped[list['WorkoutLogExercise']] = relationship(passive_deletes=True,order_by='WorkoutLogExercise.position')
    __table_args__ = (UniqueConstraint('user_id','session_id'),UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','session_id'],['workout_sessions.user_id','workout_sessions.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','plan_id'],['workout_plans.user_id','workout_plans.id'],ondelete='RESTRICT'),
        Index('ix_workout_logs_owner_date','user_id','date'),CheckConstraint('duration_minutes >= 0',name='duration'))


class WorkoutLogExercise(Identity, Owned, ExerciseFields, Base):
    __tablename__ = 'workout_log_exercises'
    log_id: Mapped[UUID]
    completed: Mapped[bool] = mapped_column(default=False)
    sets_completed: Mapped[int] = mapped_column(default=0)
    time_spent_seconds: Mapped[int] = mapped_column(default=0)
    actual_sets: Mapped[list['WorkoutSet']] = relationship(passive_deletes=True,order_by='WorkoutSet.position')
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','log_id','position'),
        ForeignKeyConstraint(['user_id','log_id'],['workout_logs.user_id','workout_logs.id'],ondelete='CASCADE'),
        CheckConstraint('sets_completed BETWEEN 0 AND sets AND time_spent_seconds >= 0',name='completion'))


class DailyWorkoutStatus(Identity, Owned, Timestamps, Base):
    __tablename__ = 'daily_workout_status'
    plan_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    log_id: Mapped[UUID | None] = mapped_column(ForeignKey('workout_logs.id',ondelete='SET NULL'))
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','plan_id','date'),
        ForeignKeyConstraint(['user_id','plan_id'],['workout_plans.user_id','workout_plans.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','log_id'],['workout_logs.user_id','workout_logs.id'],ondelete='NO ACTION'))


class DailyWorkoutCheck(Identity, Owned, Base):
    __tablename__ = 'daily_workout_checks'
    status_id: Mapped[UUID]
    exercise_index: Mapped[int]
    __table_args__ = (UniqueConstraint('user_id','status_id','exercise_index'),
        ForeignKeyConstraint(['user_id','status_id'],['daily_workout_status.user_id','daily_workout_status.id'],ondelete='CASCADE'),
        CheckConstraint('exercise_index >= 0',name='index'))


class Meal(Identity, Owned, Timestamps, Base):
    __tablename__ = 'meals'
    name: Mapped[str]
    meal_type: Mapped[str]
    date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    reported_calories: Mapped[float | None]
    reported_protein: Mapped[float | None]
    reported_carbs: Mapped[float | None]
    reported_fat: Mapped[float | None]
    source_reference: Mapped[dict | None] = mapped_column(JSONB)
    items: Mapped[list['MealItem']] = relationship(passive_deletes=True,order_by='MealItem.position')
    __table_args__ = (UniqueConstraint('user_id','id'),Index('ix_meals_owner_date','user_id','date'))


class MealItem(Identity, Owned, Base):
    __tablename__ = 'meal_items'
    meal_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    quantity: Mapped[float]
    unit: Mapped[str]
    calories: Mapped[float]
    protein: Mapped[float]
    carbs: Mapped[float]
    fat: Mapped[float]
    nutrition_evidence: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (ForeignKeyConstraint(['user_id','meal_id'],['meals.user_id','meals.id'],ondelete='CASCADE'),
        UniqueConstraint('user_id','meal_id','position'),CheckConstraint('quantity >= 0 AND calories >= 0',name='quantities'))


class WaterLog(Identity, Owned, Timestamps, Base):
    __tablename__ = 'water_logs'
    amount_ml: Mapped[int]
    date: Mapped[date] = mapped_column(Date)
    __table_args__ = (Index('ix_water_owner_date','user_id','date'),CheckConstraint('amount_ml > 0',name='amount'))


class NutritionGoal(Identity, Owned, Timestamps, Base):
    __tablename__ = 'nutrition_goals'
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_fields: Mapped[list[str] | None] = mapped_column(JSONB)
    daily_calories: Mapped[int] = mapped_column(default=2000)
    daily_protein: Mapped[float] = mapped_column(default=150)
    daily_carbs: Mapped[float] = mapped_column(default=250)
    daily_fat: Mapped[float] = mapped_column(default=65)
    water_goal_ml: Mapped[int] = mapped_column(default=2000)
    __table_args__ = (UniqueConstraint('user_id'),CheckConstraint('daily_calories > 0 AND water_goal_ml > 0',name='targets'))


class BodyMeasurement(Identity, Owned, Timestamps, Base):
    __tablename__ = 'body_measurements'
    date: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float | None]
    body_fat_percentage: Mapped[float | None]
    muscle_mass_kg: Mapped[float | None]
    bone_mass_kg: Mapped[float | None]
    water_percentage: Mapped[float | None]
    visceral_fat: Mapped[int | None]
    metabolic_age: Mapped[int | None]
    bmr_kcal: Mapped[int | None]
    height_cm: Mapped[float | None]
    neck_cm: Mapped[float | None]
    shoulders_cm: Mapped[float | None]
    chest_cm: Mapped[float | None]
    waist_cm: Mapped[float | None]
    abdomen_cm: Mapped[float | None]
    hips_cm: Mapped[float | None]
    left_arm_cm: Mapped[float | None]
    right_arm_cm: Mapped[float | None]
    left_forearm_cm: Mapped[float | None]
    right_forearm_cm: Mapped[float | None]
    left_thigh_cm: Mapped[float | None]
    right_thigh_cm: Mapped[float | None]
    left_calf_cm: Mapped[float | None]
    right_calf_cm: Mapped[float | None]
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(default='manual')
    __table_args__ = (Index('ix_measurements_owner_date','user_id','date'),CheckConstraint('height_cm IS NULL OR height_cm > 0',name='height'))


class WorkoutInsight(Identity, Owned, Timestamps, Base):
    __tablename__ = 'workout_insights'
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    total_workouts: Mapped[int] = mapped_column(default=0)
    has_measurements: Mapped[bool] = mapped_column(default=False)
    workout_types: Mapped[dict] = mapped_column(JSONB,default=dict)
    __table_args__ = (Index('ix_workout_insights_owner_created','user_id','created_at'),)


class Recipe(Identity, Owned, Timestamps, Base):
    __tablename__ = 'recipes'
    name: Mapped[str]
    description: Mapped[str] = mapped_column(Text,default='')
    instructions: Mapped[list[str]] = mapped_column(ARRAY(Text),default=list)
    prep_time_minutes: Mapped[int] = mapped_column(default=0)
    cook_time_minutes: Mapped[int] = mapped_column(default=0)
    servings: Mapped[int] = mapped_column(default=1)
    calories_per_serving: Mapped[float] = mapped_column(default=0)
    protein_per_serving: Mapped[float] = mapped_column(default=0)
    carbs_per_serving: Mapped[float] = mapped_column(default=0)
    fat_per_serving: Mapped[float] = mapped_column(default=0)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text),default=list)
    tips: Mapped[str] = mapped_column(Text,default='')
    ai_generated: Mapped[bool] = mapped_column(default=True)
    ingredients: Mapped[list['RecipeIngredient']] = relationship(passive_deletes=True,order_by='RecipeIngredient.position')
    __table_args__ = (UniqueConstraint('user_id','id'),Index('ix_recipes_owner_created','user_id','created_at'),
        CheckConstraint('servings > 0 AND prep_time_minutes >= 0 AND cook_time_minutes >= 0',name='portions_time'),
        CheckConstraint('calories_per_serving >= 0 AND protein_per_serving >= 0 AND carbs_per_serving >= 0 AND fat_per_serving >= 0',name='macros'))


class RecipeIngredient(Identity, Owned, Base):
    __tablename__ = 'recipe_ingredients'
    recipe_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    __table_args__ = (ForeignKeyConstraint(['user_id','recipe_id'],['recipes.user_id','recipes.id'],ondelete='CASCADE'),
        UniqueConstraint('user_id','recipe_id','position'))


class NutritionPlan(Identity, Owned, Timestamps, Base):
    __tablename__ = 'nutrition_plans'
    kind: Mapped[str]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(default='')
    diet_type: Mapped[str] = mapped_column(default='')
    active: Mapped[bool] = mapped_column(default=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_filename: Mapped[str | None]
    daily_calories: Mapped[float] = mapped_column(default=0)
    daily_protein: Mapped[float] = mapped_column(default=0)
    daily_carbs: Mapped[float] = mapped_column(default=0)
    daily_fat: Mapped[float] = mapped_column(default=0)
    daily_fiber: Mapped[float] = mapped_column(default=0)
    restrictions: Mapped[list[str]] = mapped_column(ARRAY(Text),default=list)
    tips: Mapped[list[str]] = mapped_column(ARRAY(Text),default=list)
    days: Mapped[list['NutritionPlanDay']] = relationship(passive_deletes=True,order_by='NutritionPlanDay.position')
    shopping_items: Mapped[list['PlanShoppingItem']] = relationship(passive_deletes=True,order_by='PlanShoppingItem.position')
    __table_args__ = (UniqueConstraint('user_id','id'),Index('ix_nutrition_plans_owner_created','user_id','created_at'),
        CheckConstraint("kind IN ('diet','generated','imported')",name='kind'),
        CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date',name='dates'))


class NutritionPlanDay(Identity, Owned, Base):
    __tablename__ = 'nutrition_plan_days'
    plan_id: Mapped[UUID]
    position: Mapped[int]
    day_name: Mapped[str]
    day_label: Mapped[str]
    calories: Mapped[float]
    meals: Mapped[list['PlannedMeal']] = relationship(passive_deletes=True,order_by='PlannedMeal.position')
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','plan_id','position'),
        ForeignKeyConstraint(['user_id','plan_id'],['nutrition_plans.user_id','nutrition_plans.id'],ondelete='CASCADE'))


class PlannedMeal(Identity, Owned, Base):
    __tablename__ = 'planned_meals'
    day_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    meal_type: Mapped[str]
    time: Mapped[str]
    preparation: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)
    calories: Mapped[float]
    protein: Mapped[float]
    carbs: Mapped[float]
    fat: Mapped[float]
    fiber: Mapped[float]
    foods: Mapped[list['PlannedFood']] = relationship(passive_deletes=True,order_by='PlannedFood.position')
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','day_id','position'),
        ForeignKeyConstraint(['user_id','day_id'],['nutrition_plan_days.user_id','nutrition_plan_days.id'],ondelete='CASCADE'))


class PlannedFood(Identity, Owned, Base):
    __tablename__ = 'planned_foods'
    meal_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    calories: Mapped[float]
    protein: Mapped[float]
    carbs: Mapped[float]
    fat: Mapped[float]
    nutrition_evidence: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint('user_id','meal_id','position'),
        ForeignKeyConstraint(['user_id','meal_id'],['planned_meals.user_id','planned_meals.id'],ondelete='CASCADE'))


class PlanShoppingItem(Identity, Owned, Base):
    __tablename__ = 'plan_shopping_items'
    plan_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    quantity: Mapped[str]
    category: Mapped[str]
    __table_args__ = (UniqueConstraint('user_id','plan_id','position'),
        ForeignKeyConstraint(['user_id','plan_id'],['nutrition_plans.user_id','nutrition_plans.id'],ondelete='CASCADE'))


class ShoppingList(Identity, Owned, Timestamps, Base):
    __tablename__ = 'shopping_lists'
    plan_id: Mapped[UUID | None]
    items: Mapped[list['ShoppingItem']] = relationship(passive_deletes=True,order_by='ShoppingItem.position')
    __table_args__ = (UniqueConstraint('user_id','id'),Index('ix_shopping_lists_owner_created','user_id','created_at'),
        ForeignKeyConstraint(['user_id','plan_id'],['nutrition_plans.user_id','nutrition_plans.id']))


class ShoppingItem(Identity, Owned, Base):
    __tablename__ = 'shopping_items'
    list_id: Mapped[UUID]
    position: Mapped[int]
    name: Mapped[str]
    quantity: Mapped[str]
    category: Mapped[str]
    checked: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint('user_id','list_id','position'),
        ForeignKeyConstraint(['user_id','list_id'],['shopping_lists.user_id','shopping_lists.id'],ondelete='CASCADE'))
