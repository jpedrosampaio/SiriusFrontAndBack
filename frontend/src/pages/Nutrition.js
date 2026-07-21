import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { getLocalDateStr } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import axios from "axios";
import ExportButtons from "@/components/ExportButtons";
import { 
  Apple, Plus, Trash2, Droplets, Target, ChefHat, 
  Flame, Drumstick, Wheat, Droplet, Settings, Sparkles,
  UtensilsCrossed, Clock, ChevronLeft, ChevronRight, Loader2,
  Coffee, Sun, Moon, Cookie, TrendingUp, BarChart3,
  Calculator, ShoppingCart, Heart, Activity, CheckSquare, Scale, ListChecks, Upload
} from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const mealTypeIcons = {
  breakfast: Coffee,
  lunch: Sun,
  dinner: Moon,
  snack: Cookie
};

const mealTypeLabels = {
  breakfast: "Café da Manhã",
  lunch: "Almoço",
  dinner: "Jantar",
  snack: "Lanche"
};

export default function Nutrition() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(getLocalDateStr());
  const [meals, setMeals] = useState([]);
  const [stats, setStats] = useState(null);
  const [goals, setGoals] = useState(null);
  const [waterData, setWaterData] = useState({ total_ml: 0 });
  const [recipes, setRecipes] = useState([]);
  const [diets, setDiets] = useState([]);
  const [showMealDialog, setShowMealDialog] = useState(false);
  const [showGoalsDialog, setShowGoalsDialog] = useState(false);
  const [showRecipeDialog, setShowRecipeDialog] = useState(false);
  const [generatingRecipe, setGeneratingRecipe] = useState(false);
  const [suggestedRecipe, setSuggestedRecipe] = useState(null);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [showRecipeDetailDialog, setShowRecipeDetailDialog] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [weeklyTrend, setWeeklyTrend] = useState(null);

  // AI Meal Plan
  const [showMealPlanDialog, setShowMealPlanDialog] = useState(false);
  const [generatingMealPlan, setGeneratingMealPlan] = useState(false);
  const [mealPlans, setMealPlans] = useState([]);
  const [mealPlanForm, setMealPlanForm] = useState({
    objective: "saude",
    restrictions: [],
    meals_per_day: 5,
    duration: "dia",
    calories_target: 0
  });
  const [selectedMealPlan, setSelectedMealPlan] = useState(null);
  const [shoppingLists, setShoppingLists] = useState([]);

  // Import Meal Plan
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importingPlan, setImportingPlan] = useState(false);
  const [importFile, setImportFile] = useState(null);

  // Health Calculator
  const [calcForm, setCalcForm] = useState({
    weight: 70, height: 170, age: 25, gender: "male",
    activity_level: "moderate", objective: "maintain"
  });
  const [calcResult, setCalcResult] = useState(null);

  // Meal form state
  const [mealForm, setMealForm] = useState({
    name: "",
    meal_type: "lunch",
    foods: [],
    notes: ""
  });

  // Food being added
  const [newFood, setNewFood] = useState({
    name: "",
    calories: 0,
    protein: 0,
    carbs: 0,
    fat: 0,
    fiber: 0,
    quantity: 1,
    weight: ""
  });
  const [estimatingFood, setEstimatingFood] = useState(false);
  const [foodEstimated, setFoodEstimated] = useState(false);

  // Goals form
  const [goalsForm, setGoalsForm] = useState({
    daily_calories: 2000,
    daily_protein: 150,
    daily_carbs: 250,
    daily_fat: 65,
    water_goal_ml: 2000
  });

  // Recipe preferences
  const [recipePreferences, setRecipePreferences] = useState({
    meal_type: "",
    diet_type: "",
    max_prep_time_minutes: 60,
    cuisine: "",
    restrictions: [],
    available_ingredients: []
  });

  useEffect(() => {
    fetchUser();
  }, []);

  useEffect(() => {
    if (user) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, selectedDate]);

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch (error) {
      window.location.href = '/login';
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [mealsRes, statsRes, goalsRes, waterRes, recipesRes, dietsRes] = await Promise.all([
        axios.get(`${API}/nutrition/meals?date=${selectedDate}`, { withCredentials: true }),
        axios.get(`${API}/nutrition/stats?date=${selectedDate}`, { withCredentials: true }),
        axios.get(`${API}/nutrition/goals`, { withCredentials: true }),
        axios.get(`${API}/nutrition/water?date=${selectedDate}`, { withCredentials: true }),
        axios.get(`${API}/nutrition/recipes`, { withCredentials: true }),
        axios.get(`${API}/nutrition/diets`, { withCredentials: true })
      ]);
      setMeals(Array.isArray(mealsRes.data) ? mealsRes.data : []);
      setStats(statsRes.data || null);
      setGoals(goalsRes.data || null);
      setGoalsForm(goalsRes.data || {});
      setWaterData(waterRes.data || { total_ml: 0, logs: [] });
      setRecipes(Array.isArray(recipesRes.data) ? recipesRes.data : []);
      setDiets(Array.isArray(dietsRes.data) ? dietsRes.data : []);
      // Fetch weekly trend
      try {
        const trendRes = await axios.get(`${API}/nutrition/weekly-trend`, { withCredentials: true });
        setWeeklyTrend(trendRes.data || null);
      } catch (e) { console.error("Weekly trend error:", e); }
    } catch (error) {
      console.error("Error fetching data:", error);
      toast.error("Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  };

  const handleAddFood = () => {
    if (!newFood.name) {
      toast.error("Digite o nome do alimento");
      return;
    }
    if (!newFood.weight) {
      toast.error("Digite a quantidade ou peso (ex: 200g, 1 unidade)");
      return;
    }
    setMealForm(prev => ({
      ...prev,
      foods: [...prev.foods, { ...newFood, estimated: foodEstimated }]
    }));
    setNewFood({ name: "", calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, quantity: 1, weight: "" });
    setFoodEstimated(false);
  };

  const handleEstimateFoodsBatch = async () => {
    const foodsToEstimate = mealForm.foods.filter(f => !f.estimated);
    if (foodsToEstimate.length === 0 && mealForm.foods.length > 0) {
      toast.info("Todos os alimentos já foram estimados!");
      return;
    }
    if (mealForm.foods.length === 0) {
      toast.error("Adicione alimentos à refeição primeiro");
      return;
    }
    setEstimatingFood(true);
    try {
      const payload = mealForm.foods.map(f => ({
        food_name: f.name,
        quantity: f.weight || "1 porção"
      }));
      const res = await axios.post(`${API}/nutrition/estimate-foods-batch`, {
        foods: payload
      }, { withCredentials: true });
      
      if (res.data.success && res.data.foods) {
        setMealForm(prev => ({
          ...prev,
          foods: prev.foods.map((food, idx) => {
            const est = res.data.foods.find(e => e.index === idx);
            if (est && est.success) {
              return {
                ...food,
                name: est.food_name || food.name,
                calories: est.calories || 0,
                protein: est.protein || 0,
                carbs: est.carbs || 0,
                fat: est.fat || 0,
                fiber: est.fiber || 0,
                estimated: true
              };
            }
            return food;
          })
        }));
        toast.success(`Nutrientes calculados para ${res.data.foods.filter(f => f.success).length} alimento(s)!`);
      } else {
        toast.error(res.data.error || "Não foi possível estimar. Tente novamente.");
      }
    } catch (error) {
      toast.error("Erro ao estimar nutrientes. Tente novamente.");
    } finally {
      setEstimatingFood(false);
    }
  };

  const handleEstimateFood = async () => {
    if (!newFood.name) {
      toast.error("Digite o nome do alimento");
      return;
    }
    if (!newFood.weight) {
      toast.error("Digite a quantidade ou peso (ex: 200g, 1 unidade, 1 xícara)");
      return;
    }
    setEstimatingFood(true);
    try {
      const res = await axios.post(`${API}/nutrition/estimate-food`, {
        food_name: newFood.name,
        quantity: newFood.weight
      }, { withCredentials: true });
      
      if (res.data.success) {
        setNewFood(prev => ({
          ...prev,
          name: res.data.food_name || prev.name,
          calories: res.data.calories || 0,
          protein: res.data.protein || 0,
          carbs: res.data.carbs || 0,
          fat: res.data.fat || 0,
          fiber: res.data.fiber || 0,
          quantity: 1
        }));
        setFoodEstimated(true);
        toast.success("Nutrientes calculados com IA!");
      } else {
        toast.error(res.data.error || "Não foi possível estimar. Tente novamente.");
      }
    } catch (error) {
      toast.error("Erro ao estimar nutrientes. Tente novamente.");
    } finally {
      setEstimatingFood(false);
    }
  };

  const handleRemoveFood = (index) => {
    setMealForm(prev => ({
      ...prev,
      foods: prev.foods.filter((_, i) => i !== index)
    }));
  };

  const handleCreateMeal = async () => {
    if (!mealForm.name || mealForm.foods.length === 0) {
      toast.error("Preencha o nome e adicione alimentos");
      return;
    }
    try {
      await axios.post(`${API}/nutrition/meals`, {
        ...mealForm,
        date: selectedDate
      }, { withCredentials: true });
      toast.success("Refeição registrada!");
      setShowMealDialog(false);
      setMealForm({ name: "", meal_type: "lunch", foods: [], notes: "" });
      fetchData();
    } catch (error) {
      toast.error("Erro ao criar refeição");
    }
  };

  const handleDeleteMeal = async (mealId) => {
    try {
      await axios.delete(`${API}/nutrition/meals/${mealId}`, { withCredentials: true });
      toast.success("Refeição removida");
      fetchData();
    } catch (error) {
      toast.error("Erro ao remover refeição");
    }
  };

  const handleUpdateGoals = async () => {
    try {
      await axios.put(`${API}/nutrition/goals`, goalsForm, { withCredentials: true });
      toast.success("Metas atualizadas!");
      setShowGoalsDialog(false);
      fetchData();
    } catch (error) {
      toast.error("Erro ao atualizar metas");
    }
  };

  const handleLogWater = async (amount) => {
    try {
      await axios.post(`${API}/nutrition/water?amount_ml=${amount}&date=${selectedDate}`, {}, { withCredentials: true });
      toast.success(`+${amount}ml de água`);
      fetchData();
    } catch (error) {
      toast.error("Erro ao registrar água");
    }
  };

  const handleSuggestRecipe = async () => {
    setGeneratingRecipe(true);
    setSuggestedRecipe(null);
    try {
      const res = await axios.post(`${API}/nutrition/recipes/suggest`, recipePreferences, { withCredentials: true });
      setSuggestedRecipe(res.data);
      toast.success("Receita sugerida!");
      fetchData();
    } catch (error) {
      toast.error("Erro ao gerar receita. Tente novamente.");
    } finally {
      setGeneratingRecipe(false);
    }
  };

  const handleDeleteRecipe = async (recipeId) => {
    try {
      await axios.delete(`${API}/nutrition/recipes/${recipeId}`, { withCredentials: true });
      toast.success("Receita removida");
      fetchData();
    } catch (error) {
      toast.error("Erro ao remover receita");
    }
  };

  const changeDate = (days) => {
    const date = new Date(selectedDate);
    date.setDate(date.getDate() + days);
    setSelectedDate(getLocalDateStr(date));
  };

  const getProgressColor = (consumed, goal) => {
    const percentage = (consumed / goal) * 100;
    if (percentage < 50) return "bg-blue-500";
    if (percentage < 80) return "bg-green-500";
    if (percentage < 100) return "bg-yellow-500";
    return "bg-red-500";
  };

  // AI Meal Plan handlers
  const handleGenerateMealPlan = async () => {
    setGeneratingMealPlan(true);
    try {
      const res = await axios.post(`${API}/nutrition/meal-plan/generate`, mealPlanForm, { withCredentials: true, timeout: 120000 });
      if (res.data.success) {
        toast.success(`Plano alimentar gerado! +${res.data.xp_earned} XP`);
        setShowMealPlanDialog(false);
        setSelectedMealPlan(res.data.plan);
        fetchMealPlans();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao gerar plano alimentar");
    } finally {
      setGeneratingMealPlan(false);
    }
  };

  const fetchMealPlans = async () => {
    try {
      const res = await axios.get(`${API}/nutrition/meal-plans`, { withCredentials: true });
      setMealPlans(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  const handleDeleteMealPlan = async (planId) => {
    try {
      await axios.delete(`${API}/nutrition/meal-plans/${planId}`, { withCredentials: true });
      toast.success("Plano removido");
      if (selectedMealPlan?.plan_id === planId) setSelectedMealPlan(null);
      fetchMealPlans();
    } catch { toast.error("Erro ao remover"); }
  };

  const handleGenerateShoppingList = async (planId) => {
    try {
      const res = await axios.post(`${API}/nutrition/shopping-list/generate`, { plan_id: planId }, { withCredentials: true });
      if (res.data.success) {
        toast.success("Lista de compras gerada!");
        setShoppingLists(prev => [res.data.shopping_list, ...prev]);
      }
    } catch { toast.error("Erro ao gerar lista"); }
  };

  const toggleShoppingItem = async (listId, idx) => {
    try {
      const res = await axios.patch(`${API}/nutrition/shopping-lists/${listId}/toggle/${idx}`, {}, { withCredentials: true });
      if (res.data.success) {
        setShoppingLists(prev => prev.map(l => l.list_id === listId ? {...l, items: res.data.items} : l));
      }
    } catch {}
  };

  const handleCalculateHealth = async () => {
    try {
      const res = await axios.post(`${API}/health/calculate`, calcForm, { withCredentials: true });
      setCalcResult(res.data);
    } catch { toast.error("Erro ao calcular"); }
  };

  const toggleMealPlanRestriction = (r) => {
    setMealPlanForm(prev => ({
      ...prev,
      restrictions: prev.restrictions.includes(r) ? prev.restrictions.filter(x => x !== r) : [...prev.restrictions, r]
    }));
  };

  const handleImportMealPlan = async () => {
    if (!importFile) {
      toast.error("Selecione um arquivo");
      return;
    }
    setImportingPlan(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      const res = await axios.post(`${API}/nutrition/import-plan`, formData, {
        withCredentials: true,
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000
      });
      if (res.data.success) {
        toast.success(`Plano importado! ${res.data.meals_created} refeições criadas. +${res.data.xp_earned} XP`);
        setShowImportDialog(false);
        setImportFile(null);
        fetchData();
        fetchMealPlans();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao importar plano alimentar");
    } finally {
      setImportingPlan(false);
    }
  };

  if (loading && !user) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#007AFF]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-white flex">
      <Sidebar user={user} />
      
      <main className="flex-1 md:ml-64 p-4 md:p-8 pb-24 md:pb-8 pt-[72px] md:pt-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-heading text-[#00F0FF]">Alimentação</h1>
            <p className="text-[#A1A1AA]">Controle sua nutrição e alcance seus objetivos</p>
          </div>
          <div className="flex items-center gap-2">
            <ExportButtons module="nutrition" />
            <Button variant="outline" size="icon" onClick={() => changeDate(-1)}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-40 bg-[#121212] border-[#27272A]"
            />
            <Button variant="outline" size="icon" onClick={() => changeDate(1)}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-[#121212] border border-[#27272A] overflow-x-auto flex-nowrap w-full justify-start md:justify-center">
            <TabsTrigger value="overview">Visão Geral</TabsTrigger>
            <TabsTrigger value="meals">Refeições</TabsTrigger>
            <TabsTrigger value="recipes">Receitas</TabsTrigger>
            <TabsTrigger value="meal_plans" onClick={fetchMealPlans}>Plano Alimentar</TabsTrigger>
            <TabsTrigger value="calculator">Calculadora</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            {/* Macros Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Calories */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Flame className="w-5 h-5 text-orange-500" />
                      <span className="font-medium">Calorias</span>
                    </div>
                    <Badge variant="outline" className="border-orange-500 text-orange-500">
                      {stats?.consumed?.calories || 0} / {goals?.daily_calories || 2000}
                    </Badge>
                  </div>
                  <Progress 
                    value={((stats?.consumed?.calories || 0) / (goals?.daily_calories || 2000)) * 100} 
                    className="h-2"
                  />
                  <p className="text-sm text-[#A1A1AA] mt-2">
                    Restam: {stats?.remaining?.calories || 0} kcal
                  </p>
                </CardContent>
              </Card>

              {/* Protein */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Drumstick className="w-5 h-5 text-red-500" />
                      <span className="font-medium">Proteína</span>
                    </div>
                    <Badge variant="outline" className="border-red-500 text-red-500">
                      {stats?.consumed?.protein || 0}g / {goals?.daily_protein || 150}g
                    </Badge>
                  </div>
                  <Progress 
                    value={((stats?.consumed?.protein || 0) / (goals?.daily_protein || 150)) * 100} 
                    className="h-2"
                  />
                  <p className="text-sm text-[#A1A1AA] mt-2">
                    Restam: {stats?.remaining?.protein || 0}g
                  </p>
                </CardContent>
              </Card>

              {/* Carbs */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Wheat className="w-5 h-5 text-yellow-500" />
                      <span className="font-medium">Carboidratos</span>
                    </div>
                    <Badge variant="outline" className="border-yellow-500 text-yellow-500">
                      {stats?.consumed?.carbs || 0}g / {goals?.daily_carbs || 250}g
                    </Badge>
                  </div>
                  <Progress 
                    value={((stats?.consumed?.carbs || 0) / (goals?.daily_carbs || 250)) * 100} 
                    className="h-2"
                  />
                  <p className="text-sm text-[#A1A1AA] mt-2">
                    Restam: {stats?.remaining?.carbs || 0}g
                  </p>
                </CardContent>
              </Card>

              {/* Fat */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Droplet className="w-5 h-5 text-purple-500" />
                      <span className="font-medium">Gordura</span>
                    </div>
                    <Badge variant="outline" className="border-purple-500 text-purple-500">
                      {stats?.consumed?.fat || 0}g / {goals?.daily_fat || 65}g
                    </Badge>
                  </div>
                  <Progress 
                    value={((stats?.consumed?.fat || 0) / (goals?.daily_fat || 65)) * 100} 
                    className="h-2"
                  />
                  <p className="text-sm text-[#A1A1AA] mt-2">
                    Restam: {stats?.remaining?.fat || 0}g
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Water and Quick Actions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Water Tracker */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Droplets className="w-5 h-5 text-blue-500" />
                    Hidratação
                  </CardTitle>
                  <CardDescription>
                    {waterData.total_ml}ml de {goals?.water_goal_ml || 2000}ml
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Progress 
                    value={(waterData.total_ml / (goals?.water_goal_ml || 2000)) * 100} 
                    className="h-4 mb-4"
                  />
                  <div className="flex flex-wrap gap-2">
                    {[200, 300, 500].map(amount => (
                      <Button
                        key={amount}
                        variant="outline"
                        onClick={() => handleLogWater(amount)}
                        className="border-blue-500/50 hover:bg-blue-500/20"
                      >
                        <Droplets className="w-4 h-4 mr-2" />
                        +{amount}ml
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardHeader>
                  <CardTitle>Ações Rápidas</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Dialog open={showMealDialog} onOpenChange={setShowMealDialog}>
                    <DialogTrigger asChild>
                      <Button className="w-full bg-[#007AFF] hover:bg-[#0066CC]">
                        <Plus className="w-4 h-4 mr-2" />
                        Registrar Refeição
                      </Button>
                    </DialogTrigger>
                  </Dialog>

                  <Dialog open={showGoalsDialog} onOpenChange={setShowGoalsDialog}>
                    <DialogTrigger asChild>
                      <Button variant="outline" className="w-full">
                        <Target className="w-4 h-4 mr-2" />
                        Definir Metas
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                      <DialogHeader>
                        <DialogTitle>Metas Nutricionais</DialogTitle>
                        <DialogDescription>Configure suas metas diárias</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div>
                          <Label>Calorias Diárias</Label>
                          <Input
                            type="number"
                            value={goalsForm.daily_calories}
                            onChange={(e) => setGoalsForm({...goalsForm, daily_calories: Number(e.target.value)})}
                            className="bg-[#121212] border-[#27272A]"
                          />
                        </div>
                        <div>
                          <Label>Proteína (g)</Label>
                          <Input
                            type="number"
                            value={goalsForm.daily_protein}
                            onChange={(e) => setGoalsForm({...goalsForm, daily_protein: Number(e.target.value)})}
                            className="bg-[#121212] border-[#27272A]"
                          />
                        </div>
                        <div>
                          <Label>Carboidratos (g)</Label>
                          <Input
                            type="number"
                            value={goalsForm.daily_carbs}
                            onChange={(e) => setGoalsForm({...goalsForm, daily_carbs: Number(e.target.value)})}
                            className="bg-[#121212] border-[#27272A]"
                          />
                        </div>
                        <div>
                          <Label>Gordura (g)</Label>
                          <Input
                            type="number"
                            value={goalsForm.daily_fat}
                            onChange={(e) => setGoalsForm({...goalsForm, daily_fat: Number(e.target.value)})}
                            className="bg-[#121212] border-[#27272A]"
                          />
                        </div>
                        <div>
                          <Label>Água (ml)</Label>
                          <Input
                            type="number"
                            value={goalsForm.water_goal_ml}
                            onChange={(e) => setGoalsForm({...goalsForm, water_goal_ml: Number(e.target.value)})}
                            className="bg-[#121212] border-[#27272A]"
                          />
                        </div>
                        <Button onClick={handleUpdateGoals} className="w-full bg-[#007AFF]">
                          Salvar Metas
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>

                  <Button variant="outline" className="w-full border-green-500/50 hover:bg-green-500/20" onClick={() => setShowRecipeDialog(true)}>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Sugerir Receita com IA
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Today's Meals Summary */}
            <Card className="bg-[#0A0A0A] border-[#27272A]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UtensilsCrossed className="w-5 h-5 text-[#007AFF]" />
                  Refeições de Hoje ({meals.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {meals.length === 0 ? (
                  <p className="text-center text-[#A1A1AA] py-8">
                    Nenhuma refeição registrada hoje
                  </p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {meals.map(meal => {
                      const MealIcon = mealTypeIcons[meal.meal_type] || UtensilsCrossed;
                      return (
                        <div key={meal.meal_id} className="bg-[#121212] p-4 rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <MealIcon className="w-4 h-4 text-[#007AFF]" />
                              <span className="font-medium">{meal.name}</span>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => handleDeleteMeal(meal.meal_id)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </div>
                          <Badge variant="outline" className="mb-2">{mealTypeLabels[meal.meal_type]}</Badge>
                          <div className="grid grid-cols-4 gap-2 text-xs text-[#A1A1AA]">
                            <span>{meal.total_calories} kcal</span>
                            <span>{meal.total_protein}g P</span>
                            <span>{meal.total_carbs}g C</span>
                            <span>{meal.total_fat}g G</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Weekly Nutrition Charts */}
            {weeklyTrend && weeklyTrend.daily && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Calorie Trend */}
                <Card className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><Flame className="w-4 h-4 text-orange-400" />Calorias - Últimos 7 Dias</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={weeklyTrend.daily}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                        <XAxis dataKey="day" tick={{ fill: '#71717A', fontSize: 11 }} />
                        <YAxis tick={{ fill: '#71717A', fontSize: 10 }} />
                        <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} />
                        <Bar dataKey="calorias" fill="#FF9500" name="Calorias" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                    {weeklyTrend.goals && (
                      <div className="flex justify-between text-[10px] text-[#71717A] mt-2 px-2">
                        <span>Meta: {weeklyTrend.goals.daily_calories} kcal/dia</span>
                        <span>Média: {weeklyTrend.averages?.calorias || 0} kcal</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Macro Distribution */}
                <Card className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="w-4 h-4 text-[#007AFF]" />Macronutrientes - Semana</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={weeklyTrend.daily}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                        <XAxis dataKey="day" tick={{ fill: '#71717A', fontSize: 11 }} />
                        <YAxis tick={{ fill: '#71717A', fontSize: 10 }} unit="g" />
                        <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} formatter={(v) => `${v}g`} />
                        <Line type="monotone" dataKey="proteina" stroke="#EF4444" strokeWidth={2} name="Proteína" dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="carboidratos" stroke="#F59E0B" strokeWidth={2} name="Carboidratos" dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="gordura" stroke="#8B5CF6" strokeWidth={2} name="Gordura" dot={{ r: 3 }} />
                        <Legend />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Water Trend */}
                <Card className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><Droplets className="w-4 h-4 text-blue-400" />Hidratação - Semana</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={weeklyTrend.daily}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                        <XAxis dataKey="day" tick={{ fill: '#71717A', fontSize: 11 }} />
                        <YAxis tick={{ fill: '#71717A', fontSize: 10 }} unit="ml" />
                        <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff', fontSize: 11 }} formatter={(v) => `${v}ml`} />
                        <Bar dataKey="agua_ml" fill="#3B82F6" name="Água (ml)" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                    {weeklyTrend.goals && (
                      <p className="text-[10px] text-[#71717A] text-center mt-1">Meta: {weeklyTrend.goals.water_goal_ml}ml/dia</p>
                    )}
                  </CardContent>
                </Card>

                {/* Macro Summary Today */}
                {stats && stats.consumed && (
                  <Card className="bg-[#0A0A0A] border-[#27272A]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2"><Target className="w-4 h-4 text-green-400" />Macros Hoje</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={180}>
                        <PieChart>
                          <Pie
                            data={[
                              { name: 'Proteína', value: stats.consumed.protein || 0 },
                              { name: 'Carboidratos', value: stats.consumed.carbs || 0 },
                              { name: 'Gordura', value: stats.consumed.fat || 0 }
                            ].filter(d => d.value > 0)}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={65}
                            label={(e) => `${e.name}: ${e.value}g`}
                          >
                            <Cell fill="#EF4444" />
                            <Cell fill="#F59E0B" />
                            <Cell fill="#8B5CF6" />
                          </Pie>
                          <Tooltip formatter={(v) => `${v}g`} />
                        </PieChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </TabsContent>

          {/* Meals Tab */}
          <TabsContent value="meals" className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold">Refeições</h2>
              <Button onClick={() => setShowMealDialog(true)} className="bg-[#007AFF]">
                <Plus className="w-4 h-4 mr-2" />
                Nova Refeição
              </Button>
            </div>

            {["breakfast", "lunch", "dinner", "snack"].map(mealType => {
              const typeMeals = meals.filter(m => m.meal_type === mealType);
              const MealIcon = mealTypeIcons[mealType];
              
              return (
                <Card key={mealType} className="bg-[#0A0A0A] border-[#27272A]">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <MealIcon className="w-5 h-5" />
                      {mealTypeLabels[mealType]}
                      <Badge variant="outline">{typeMeals.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {typeMeals.length === 0 ? (
                      <p className="text-[#A1A1AA] text-center py-4">Nenhuma refeição registrada</p>
                    ) : (
                      <div className="space-y-3">
                        {typeMeals.map(meal => (
                          <div key={meal.meal_id} className="bg-[#121212] p-4 rounded-lg">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="font-medium">{meal.name}</h4>
                              <Button variant="ghost" size="icon" onClick={() => handleDeleteMeal(meal.meal_id)}>
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </div>
                            <div className="grid grid-cols-4 gap-4 mb-3">
                              <div className="text-center">
                                <Flame className="w-4 h-4 mx-auto text-orange-500" />
                                <span className="text-sm">{meal.total_calories} kcal</span>
                              </div>
                              <div className="text-center">
                                <Drumstick className="w-4 h-4 mx-auto text-red-500" />
                                <span className="text-sm">{meal.total_protein}g</span>
                              </div>
                              <div className="text-center">
                                <Wheat className="w-4 h-4 mx-auto text-yellow-500" />
                                <span className="text-sm">{meal.total_carbs}g</span>
                              </div>
                              <div className="text-center">
                                <Droplet className="w-4 h-4 mx-auto text-purple-500" />
                                <span className="text-sm">{meal.total_fat}g</span>
                              </div>
                            </div>
                            {meal.foods?.length > 0 && (
                              <div className="border-t border-[#27272A] pt-3 mt-3">
                                <span className="text-xs text-[#A1A1AA]">Alimentos:</span>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {meal.foods.map((food, idx) => (
                                    <Badge key={idx} variant="secondary" className="text-xs">
                                      {food.name} x{food.quantity}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </TabsContent>

          {/* Recipes Tab */}
          <TabsContent value="recipes" className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold">Minhas Receitas</h2>
              <Button onClick={() => setShowRecipeDialog(true)} className="bg-green-600 hover:bg-green-700">
                <Sparkles className="w-4 h-4 mr-2" />
                Nova Receita com IA
              </Button>
            </div>

            {recipes.length === 0 ? (
              <Card className="bg-[#0A0A0A] border-[#27272A]">
                <CardContent className="text-center py-12">
                  <ChefHat className="w-12 h-12 mx-auto text-[#A1A1AA] mb-4" />
                  <h3 className="text-lg font-medium mb-2">Nenhuma receita salva</h3>
                  <p className="text-[#A1A1AA] mb-4">Use a IA para gerar receitas personalizadas!</p>
                  <Button onClick={() => setShowRecipeDialog(true)} className="bg-green-600">
                    <Sparkles className="w-4 h-4 mr-2" />
                    Gerar Receita
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {recipes.map(recipe => (
                  <Card key={recipe.recipe_id} className="bg-[#0A0A0A] border-[#27272A] cursor-pointer hover:border-[#3F3F46] transition-colors" onClick={() => { setSelectedRecipe(recipe); setShowRecipeDetailDialog(true); }}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle className="text-lg">{recipe.name}</CardTitle>
                          <CardDescription>{recipe.description}</CardDescription>
                        </div>
                        <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); handleDeleteRecipe(recipe.recipe_id); }}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-2 mb-4">
                        <div className="flex items-center gap-1 text-sm text-[#A1A1AA]">
                          <Clock className="w-4 h-4" />
                          {recipe.prep_time_minutes + recipe.cook_time_minutes}min
                        </div>
                        <div className="flex items-center gap-1 text-sm text-[#A1A1AA]">
                          <UtensilsCrossed className="w-4 h-4" />
                          {recipe.servings} porções
                        </div>
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-center text-xs">
                        <div>
                          <span className="text-orange-500">{recipe.calories_per_serving}</span>
                          <span className="block text-[#A1A1AA]">kcal</span>
                        </div>
                        <div>
                          <span className="text-red-500">{recipe.protein_per_serving}g</span>
                          <span className="block text-[#A1A1AA]">P</span>
                        </div>
                        <div>
                          <span className="text-yellow-500">{recipe.carbs_per_serving}g</span>
                          <span className="block text-[#A1A1AA]">C</span>
                        </div>
                        <div>
                          <span className="text-purple-500">{recipe.fat_per_serving}g</span>
                          <span className="block text-[#A1A1AA]">G</span>
                        </div>
                      </div>
                      {recipe.ai_generated && (
                        <Badge className="mt-3 bg-green-500/20 text-green-400">
                          <Sparkles className="w-3 h-3 mr-1" />
                          Gerada por IA
                        </Badge>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Recipe Detail Dialog */}
              <Dialog open={showRecipeDetailDialog} onOpenChange={setShowRecipeDetailDialog}>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
                  {selectedRecipe && (
                    <>
                      <DialogHeader>
                        <DialogTitle className="text-xl">{selectedRecipe.name}</DialogTitle>
                        <DialogDescription>{selectedRecipe.description}</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-6 py-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <div className="bg-[#121212] p-3 rounded-lg text-center">
                            <Clock className="w-5 h-5 mx-auto mb-1 text-blue-400" />
                            <p className="text-sm font-bold">{selectedRecipe.prep_time_minutes}min</p>
                            <p className="text-xs text-[#A1A1AA]">Preparo</p>
                          </div>
                          <div className="bg-[#121212] p-3 rounded-lg text-center">
                            <Flame className="w-5 h-5 mx-auto mb-1 text-orange-400" />
                            <p className="text-sm font-bold">{selectedRecipe.cook_time_minutes}min</p>
                            <p className="text-xs text-[#A1A1AA]">Cozimento</p>
                          </div>
                          <div className="bg-[#121212] p-3 rounded-lg text-center">
                            <UtensilsCrossed className="w-5 h-5 mx-auto mb-1 text-green-400" />
                            <p className="text-sm font-bold">{selectedRecipe.servings}</p>
                            <p className="text-xs text-[#A1A1AA]">Porções</p>
                          </div>
                          <div className="bg-[#121212] p-3 rounded-lg text-center">
                            <Target className="w-5 h-5 mx-auto mb-1 text-red-400" />
                            <p className="text-sm font-bold">{selectedRecipe.calories_per_serving}</p>
                            <p className="text-xs text-[#A1A1AA]">kcal/porção</p>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="bg-red-500/10 p-3 rounded-lg text-center">
                            <p className="text-lg font-bold text-red-400">{selectedRecipe.protein_per_serving}g</p>
                            <p className="text-xs text-[#A1A1AA]">Proteínas</p>
                          </div>
                          <div className="bg-yellow-500/10 p-3 rounded-lg text-center">
                            <p className="text-lg font-bold text-yellow-400">{selectedRecipe.carbs_per_serving}g</p>
                            <p className="text-xs text-[#A1A1AA]">Carboidratos</p>
                          </div>
                          <div className="bg-purple-500/10 p-3 rounded-lg text-center">
                            <p className="text-lg font-bold text-purple-400">{selectedRecipe.fat_per_serving}g</p>
                            <p className="text-xs text-[#A1A1AA]">Gorduras</p>
                          </div>
                        </div>
                        {selectedRecipe.ingredients && selectedRecipe.ingredients.length > 0 && (
                          <div>
                            <h3 className="font-bold text-base mb-3 flex items-center gap-2">
                              <Apple className="w-4 h-4 text-green-400" /> Ingredientes
                            </h3>
                            <div className="bg-[#121212] rounded-lg p-4">
                              <ul className="space-y-2">
                                {selectedRecipe.ingredients.map((ingredient, idx) => (
                                  <li key={idx} className="flex items-start gap-2 text-sm">
                                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 shrink-0" />
                                    <span className="text-[#E4E4E7]">
                                      {typeof ingredient === 'object' && ingredient !== null
                                        ? `${ingredient.quantity || ''} ${ingredient.unit || ''} de ${ingredient.name || ''}`.trim()
                                        : String(ingredient)}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                        {selectedRecipe.instructions && selectedRecipe.instructions.length > 0 && (
                          <div>
                            <h3 className="font-bold text-base mb-3 flex items-center gap-2">
                              <ChefHat className="w-4 h-4 text-orange-400" /> Modo de Preparo
                            </h3>
                            <div className="space-y-3">
                              {selectedRecipe.instructions.map((step, idx) => (
                                <div key={idx} className="flex items-start gap-3 bg-[#121212] p-3 rounded-lg">
                                  <span className="bg-orange-500/20 text-orange-400 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0">{idx + 1}</span>
                                  <p className="text-sm text-[#E4E4E7]">{typeof step === 'object' ? JSON.stringify(step) : String(step)}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {selectedRecipe.tips && (Array.isArray(selectedRecipe.tips) ? selectedRecipe.tips.length > 0 : selectedRecipe.tips.length > 0) && (
                          <div>
                            <h3 className="font-bold text-base mb-3 flex items-center gap-2">
                              <Sparkles className="w-4 h-4 text-[#00F0FF]" /> Dicas
                            </h3>
                            <div className="bg-[#00F0FF]/5 border border-[#00F0FF]/20 rounded-lg p-4">
                              <ul className="space-y-2">
                                {(Array.isArray(selectedRecipe.tips) ? selectedRecipe.tips : [selectedRecipe.tips]).map((tip, idx) => (
                                  <li key={idx} className="flex items-start gap-2 text-sm">
                                    <span className="text-[#00F0FF]">💡</span>
                                    <span className="text-[#E4E4E7]">{typeof tip === 'object' ? JSON.stringify(tip) : String(tip)}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                        {selectedRecipe.tags && selectedRecipe.tags.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {selectedRecipe.tags.map((tag, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">{tag}</Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </DialogContent>
              </Dialog>
              </>
            )}
          </TabsContent>
          {/* AI Meal Plan Tab */}
          <TabsContent value="meal_plans" className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold">Planos Alimentares com IA</h2>
              <div className="flex gap-2">
                {/* Import Plan Dialog */}
                <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
                  <DialogTrigger asChild>
                    <Button data-testid="import-meal-plan-btn" variant="outline" className="border-[#27272A] text-white hover:bg-[#1A1A2E]">
                      <Upload className="w-4 h-4 mr-2" /> Importar Plano
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2"><Upload className="w-5 h-5 text-[#00F0FF]" /> Importar Plano Alimentar</DialogTitle>
                      <DialogDescription className="text-[#A1A1AA]">Envie um PDF ou foto do seu plano alimentar. A IA vai extrair as refeições automaticamente.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div 
                        data-testid="import-drop-zone"
                        onClick={() => document.getElementById('import-file-input').click()}
                        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                          importFile ? 'border-[#00F0FF] bg-[#00F0FF]/5' : 'border-[#27272A] hover:border-[#A855F7]'
                        }`}
                      >
                        <input
                          id="import-file-input"
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png,.webp"
                          className="hidden"
                          onChange={(e) => setImportFile(e.target.files[0] || null)}
                        />
                        {importFile ? (
                          <div>
                            <CheckSquare className="w-8 h-8 mx-auto text-[#00F0FF] mb-2" />
                            <p className="text-sm font-medium text-[#00F0FF]">{importFile.name}</p>
                            <p className="text-xs text-[#71717A] mt-1">{(importFile.size / 1024).toFixed(0)} KB</p>
                            <button onClick={(e) => { e.stopPropagation(); setImportFile(null); }} className="text-xs text-red-400 mt-2 hover:underline">Remover</button>
                          </div>
                        ) : (
                          <div>
                            <Upload className="w-8 h-8 mx-auto text-[#71717A] mb-2" />
                            <p className="text-sm text-[#A1A1AA]">Clique para selecionar</p>
                            <p className="text-xs text-[#52525B] mt-1">PDF, JPG, PNG ou WEBP</p>
                          </div>
                        )}
                      </div>
                      <div className="bg-[#121212] rounded-lg p-3 border border-[#27272A]">
                        <p className="text-xs text-[#A1A1AA]">
                          <Sparkles className="w-3 h-3 inline mr-1 text-[#A855F7]" />
                          A IA vai extrair: refeições, calorias, macros, horários e dicas do nutricionista. As refeições serão adicionadas ao dia de hoje.
                        </p>
                      </div>
                      <Button 
                        data-testid="import-plan-submit-btn"
                        onClick={handleImportMealPlan} 
                        disabled={!importFile || importingPlan} 
                        className="w-full bg-gradient-to-r from-[#00F0FF] to-[#007AFF] text-white"
                      >
                        {importingPlan ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Importando...</> : <><Upload className="w-4 h-4 mr-2" /> Importar Plano</>}
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
                {/* Generate Plan Dialog */}
                <Dialog open={showMealPlanDialog} onOpenChange={setShowMealPlanDialog}>
                  <DialogTrigger asChild>
                    <Button className="bg-gradient-to-r from-[#A855F7] to-[#00F0FF] text-white">
                      <Sparkles className="w-4 h-4 mr-2" /> Gerar Plano com IA
                    </Button>
                  </DialogTrigger>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2"><Sparkles className="w-5 h-5 text-[#A855F7]" /> Gerar Plano Alimentar</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div>
                      <Label className="text-xs uppercase">Objetivo</Label>
                      <Select value={mealPlanForm.objective} onValueChange={(v) => setMealPlanForm({...mealPlanForm, objective: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                          <SelectItem value="saude">Saúde geral</SelectItem>
                          <SelectItem value="emagrecimento">Emagrecimento</SelectItem>
                          <SelectItem value="hipertrofia">Hipertrofia</SelectItem>
                          <SelectItem value="definicao">Definição muscular</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs uppercase">Duração</Label>
                      <Select value={mealPlanForm.duration} onValueChange={(v) => setMealPlanForm({...mealPlanForm, duration: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white">
                          <SelectItem value="dia">1 Dia</SelectItem>
                          <SelectItem value="semana">1 Semana</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs uppercase">Refeições por dia</Label>
                      <div className="flex gap-2 mt-1">
                        {[3, 4, 5, 6].map(n => (
                          <button key={n} onClick={() => setMealPlanForm({...mealPlanForm, meals_per_day: n})}
                            className={`flex-1 py-2 rounded text-sm ${mealPlanForm.meals_per_day === n ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA] border border-[#27272A]'}`}>
                            {n}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs uppercase">Meta calórica (0 = automática)</Label>
                      <Input type="number" value={mealPlanForm.calories_target} onChange={(e) => setMealPlanForm({...mealPlanForm, calories_target: parseInt(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs uppercase mb-2 block">Restrições</Label>
                      <div className="flex flex-wrap gap-2">
                        {["vegetariano", "vegano", "sem_gluten", "sem_lactose", "low_carb"].map(r => (
                          <button key={r} onClick={() => toggleMealPlanRestriction(r)}
                            className={`px-3 py-1.5 rounded-full text-xs ${mealPlanForm.restrictions.includes(r) ? 'bg-[#A855F7] text-white' : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA]'}`}>
                            {r.replace('_', ' ')}
                          </button>
                        ))}
                      </div>
                    </div>
                    <Button onClick={handleGenerateMealPlan} disabled={generatingMealPlan} className="w-full bg-gradient-to-r from-[#A855F7] to-[#00F0FF] text-white">
                      {generatingMealPlan ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando...</> : <><Sparkles className="w-4 h-4 mr-2" /> Gerar Plano</>}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
              </div>
            </div>
            {mealPlans.length === 0 && !selectedMealPlan ? (
              <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-12"><Apple className="w-12 h-12 mx-auto text-[#A1A1AA] mb-4" /><h3 className="text-lg font-medium mb-2">Nenhum plano alimentar</h3><p className="text-[#A1A1AA]">Gere um plano personalizado com IA</p></CardContent></Card>
            ) : (
              <div className="space-y-4">
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {(selectedMealPlan ? [selectedMealPlan, ...mealPlans.filter(p => p.plan_id !== selectedMealPlan.plan_id)] : mealPlans).map(plan => (
                    <button key={plan.plan_id} onClick={() => setSelectedMealPlan(plan)}
                      className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap ${selectedMealPlan?.plan_id === plan.plan_id ? 'bg-[#007AFF] text-white' : 'bg-[#121212] border border-[#27272A] text-[#A1A1AA]'}`}>
                      {plan.name || "Plano"}
                    </button>
                  ))}
                </div>
                {selectedMealPlan && (
                  <div className="space-y-4">
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="text-lg font-bold">{selectedMealPlan.name}</h3>
                          <p className="text-sm text-[#A1A1AA]">{selectedMealPlan.description}</p>
                          <div className="flex gap-4 mt-3 text-sm">
                            <span className="text-[#FF9500]">{selectedMealPlan.calories_total || '---'} kcal</span>
                            <span className="text-[#FF6B6B]">{selectedMealPlan.macros?.protein_g || 0}g P</span>
                            <span className="text-[#FFD700]">{selectedMealPlan.macros?.carbs_g || 0}g C</span>
                            <span className="text-[#00B4D8]">{selectedMealPlan.macros?.fat_g || 0}g G</span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => handleGenerateShoppingList(selectedMealPlan.plan_id)} className="border-[#27272A] text-xs"><ShoppingCart className="w-3 h-3 mr-1" /> Lista</Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteMealPlan(selectedMealPlan.plan_id)} className="text-red-400"><Trash2 className="w-4 h-4" /></Button>
                        </div>
                      </div>
                    </Card>
                    {(selectedMealPlan.days || []).map((day, dIdx) => (
                      <Card key={dIdx} className="bg-[#0A0A0A] border-[#27272A] p-4">
                        <h4 className="font-bold text-sm uppercase text-[#00F0FF] mb-3">{day.day_label || `Dia ${dIdx + 1}`}</h4>
                        <div className="space-y-3">
                          {(day.meals || []).map((meal, mIdx) => (
                            <div key={mIdx} className="bg-[#121212] rounded-lg p-3">
                              <div className="flex justify-between items-center mb-2">
                                <span className="text-sm font-medium">{meal.time} - {meal.name}</span>
                                <Badge variant="outline" className="text-[10px]">{meal.total_calories || 0} kcal</Badge>
                              </div>
                              {meal.foods && meal.foods.map((f, fIdx) => (
                                <div key={fIdx} className="flex justify-between text-xs text-[#A1A1AA]"><span>{f.name} ({f.quantity})</span><span>{f.calories} kcal</span></div>
                              ))}
                              {meal.preparation && <p className="text-xs text-[#52525B] mt-2 italic">{meal.preparation}</p>}
                            </div>
                          ))}
                        </div>
                      </Card>
                    ))}
                    {selectedMealPlan.tips && selectedMealPlan.tips.length > 0 && (
                      <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                        <h4 className="font-bold text-sm text-[#FFD700] mb-2">Dicas</h4>
                        <ul className="space-y-1">{selectedMealPlan.tips.map((tip, i) => (<li key={i} className="text-xs text-[#A1A1AA]">• {tip}</li>))}</ul>
                      </Card>
                    )}
                    {shoppingLists.length > 0 && (
                      <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                        <h4 className="font-bold text-sm text-green-400 mb-3">Lista de Compras</h4>
                        <div className="space-y-1">
                          {shoppingLists[0].items?.map((item, idx) => (
                            <div key={idx} onClick={() => toggleShoppingItem(shoppingLists[0].list_id, idx)}
                              className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${item.checked ? 'text-[#52525B] line-through' : 'text-white'} hover:bg-[#121212]`}>
                              {item.checked ? <CheckSquare className="w-4 h-4 text-green-500" /> : <div className="w-4 h-4 border border-[#52525B] rounded" />}
                              <span className="flex-1">{item.name}</span><span className="text-xs text-[#52525B]">{item.quantity}</span>
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* Health Calculator Tab */}
          <TabsContent value="calculator" className="space-y-6">
            <h2 className="text-xl font-bold flex items-center gap-2"><Calculator className="w-5 h-5 text-[#00F0FF]" /> Calculadora de Saúde</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                <h3 className="font-bold mb-4">Seus Dados</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label className="text-xs">Peso (kg)</Label><Input type="number" value={calcForm.weight} onChange={(e) => setCalcForm({...calcForm, weight: parseFloat(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white mt-1" /></div>
                    <div><Label className="text-xs">Altura (cm)</Label><Input type="number" value={calcForm.height} onChange={(e) => setCalcForm({...calcForm, height: parseFloat(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white mt-1" /></div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label className="text-xs">Idade</Label><Input type="number" value={calcForm.age} onChange={(e) => setCalcForm({...calcForm, age: parseInt(e.target.value) || 0})} className="bg-[#121212] border-[#27272A] text-white mt-1" /></div>
                    <div><Label className="text-xs">Sexo</Label>
                      <Select value={calcForm.gender} onValueChange={(v) => setCalcForm({...calcForm, gender: v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#121212] border-[#27272A] text-white"><SelectItem value="male">Masculino</SelectItem><SelectItem value="female">Feminino</SelectItem></SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div><Label className="text-xs">Nível de Atividade</Label>
                    <Select value={calcForm.activity_level} onValueChange={(v) => setCalcForm({...calcForm, activity_level: v})}>
                      <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#121212] border-[#27272A] text-white"><SelectItem value="sedentary">Sedentário</SelectItem><SelectItem value="light">Leve (1-3x/sem)</SelectItem><SelectItem value="moderate">Moderado (3-5x/sem)</SelectItem><SelectItem value="active">Ativo (6-7x/sem)</SelectItem><SelectItem value="very_active">Muito ativo</SelectItem></SelectContent>
                    </Select>
                  </div>
                  <div><Label className="text-xs">Objetivo</Label>
                    <Select value={calcForm.objective} onValueChange={(v) => setCalcForm({...calcForm, objective: v})}>
                      <SelectTrigger className="bg-[#121212] border-[#27272A] text-white mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#121212] border-[#27272A] text-white"><SelectItem value="lose">Emagrecer</SelectItem><SelectItem value="maintain">Manter</SelectItem><SelectItem value="gain">Ganhar massa</SelectItem></SelectContent>
                    </Select>
                  </div>
                  <Button onClick={handleCalculateHealth} className="w-full bg-[#00F0FF] text-black hover:bg-[#00D4E5]"><Calculator className="w-4 h-4 mr-2" /> Calcular</Button>
                </div>
              </Card>
              <div className="space-y-4">
                {calcResult ? (
                  <>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                      <h3 className="font-bold mb-4">Resultados</h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#121212] rounded-lg p-4 text-center"><Scale className="w-6 h-6 mx-auto mb-2 text-[#00F0FF]" /><p className="font-data text-2xl">{calcResult.bmi}</p><p className="text-xs text-[#A1A1AA]">IMC</p><p className={`text-xs mt-1 ${calcResult.bmi >= 18.5 && calcResult.bmi < 25 ? 'text-[#39FF14]' : 'text-[#FF9500]'}`}>{calcResult.bmi_class}</p></div>
                        <div className="bg-[#121212] rounded-lg p-4 text-center"><Flame className="w-6 h-6 mx-auto mb-2 text-[#FF9500]" /><p className="font-data text-2xl">{calcResult.bmr}</p><p className="text-xs text-[#A1A1AA]">TMB (kcal)</p></div>
                        <div className="bg-[#121212] rounded-lg p-4 text-center"><Activity className="w-6 h-6 mx-auto mb-2 text-[#A855F7]" /><p className="font-data text-2xl">{calcResult.tdee}</p><p className="text-xs text-[#A1A1AA]">GET (kcal)</p></div>
                        <div className="bg-[#121212] rounded-lg p-4 text-center"><Target className="w-6 h-6 mx-auto mb-2 text-[#39FF14]" /><p className="font-data text-2xl text-[#39FF14]">{calcResult.calories_target}</p><p className="text-xs text-[#A1A1AA]">Meta (kcal)</p></div>
                      </div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                      <h3 className="font-bold mb-4">Macros Recomendados</h3>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-[#121212] rounded-lg p-3 text-center"><p className="font-data text-xl text-[#FF6B6B]">{calcResult.macros.protein_g}g</p><p className="text-xs text-[#A1A1AA]">Proteína ({calcResult.macros.protein_pct}%)</p></div>
                        <div className="bg-[#121212] rounded-lg p-3 text-center"><p className="font-data text-xl text-[#FFD700]">{calcResult.macros.carbs_g}g</p><p className="text-xs text-[#A1A1AA]">Carboidratos ({calcResult.macros.carbs_pct}%)</p></div>
                        <div className="bg-[#121212] rounded-lg p-3 text-center"><p className="font-data text-xl text-[#00B4D8]">{calcResult.macros.fat_g}g</p><p className="text-xs text-[#A1A1AA]">Gordura ({calcResult.macros.fat_pct}%)</p></div>
                      </div>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="flex justify-between"><span className="text-[#A1A1AA]">Peso ideal:</span><span className="font-data">{calcResult.ideal_weight.min}-{calcResult.ideal_weight.max} kg</span></div>
                        <div className="flex justify-between"><span className="text-[#A1A1AA]">Água/dia:</span><span className="font-data text-[#00B4D8]">{calcResult.water_liters}L</span></div>
                      </div>
                    </Card>
                  </>
                ) : (
                  <Card className="bg-[#0A0A0A] border-[#27272A]"><CardContent className="text-center py-12"><Calculator className="w-12 h-12 mx-auto text-[#A1A1AA] mb-4" /><h3 className="text-lg font-medium mb-2">Calculadora de Saúde</h3><p className="text-[#A1A1AA] text-sm">Preencha seus dados para ver IMC, TMB, GET e macros</p></CardContent></Card>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Meal Dialog - Outside Tabs so it works from any tab */}
        <Dialog open={showMealDialog} onOpenChange={setShowMealDialog}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Nova Refeição</DialogTitle>
              <DialogDescription>Registre sua refeição com os alimentos consumidos</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Nome da Refeição</Label>
                  <Input
                    value={mealForm.name}
                    onChange={(e) => setMealForm({...mealForm, name: e.target.value})}
                    placeholder="Ex: Almoço completo"
                    className="bg-[#121212] border-[#27272A]"
                  />
                </div>
                <div>
                  <Label>Tipo</Label>
                  <Select value={mealForm.meal_type} onValueChange={(v) => setMealForm({...mealForm, meal_type: v})}>
                    <SelectTrigger className="bg-[#121212] border-[#27272A]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="breakfast">Café da Manhã</SelectItem>
                      <SelectItem value="lunch">Almoço</SelectItem>
                      <SelectItem value="dinner">Jantar</SelectItem>
                      <SelectItem value="snack">Lanche</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Add Food Section */}
              <div className="border border-[#27272A] rounded-lg p-4">
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <Plus className="w-4 h-4 text-[#007AFF]" />
                  Adicionar Alimento
                </h4>
                
                {/* Step 1: Food name + weight */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                  <div>
                    <Label className="text-xs text-[#A1A1AA] mb-1 block">Alimento</Label>
                    <Input
                      placeholder="Ex: Arroz, Frango grelhado, Banana..."
                      value={newFood.name}
                      onChange={(e) => { setNewFood({...newFood, name: e.target.value}); setFoodEstimated(false); }}
                      className="bg-[#121212] border-[#27272A]"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-[#A1A1AA] mb-1 block">Quantidade / Peso</Label>
                    <Input
                      placeholder="Ex: 200g, 1 xícara, 2 unidades..."
                      value={newFood.weight}
                      onChange={(e) => { setNewFood({...newFood, weight: e.target.value}); setFoodEstimated(false); }}
                      className="bg-[#121212] border-[#27272A]"
                    />
                  </div>
                </div>

                <Button onClick={handleAddFood} variant="outline" className="w-full" disabled={!newFood.name || !newFood.weight}>
                  <Plus className="w-4 h-4 mr-2" />
                  Adicionar à Lista
                </Button>
              </div>

              {/* Foods List */}
              {mealForm.foods.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">Alimentos ({mealForm.foods.length})</h4>
                    {mealForm.foods.some(f => f.estimated) && (
                      <span className="text-xs text-green-400 flex items-center gap-1">
                        <CheckSquare className="w-3 h-3" /> Nutrientes estimados
                      </span>
                    )}
                  </div>
                  {mealForm.foods.map((food, idx) => (
                    <div key={idx} className={`flex items-center justify-between p-3 rounded-lg border ${food.estimated ? 'bg-[#121212] border-green-500/30' : 'bg-[#121212] border-[#27272A]'}`}>
                      <div className="flex-1">
                        <span className="font-medium">{food.name}</span>
                        {food.weight && <span className="text-xs text-[#52525B] ml-2">({food.weight})</span>}
                        {food.estimated ? (
                          <div className="flex gap-3 mt-1 text-xs text-[#A1A1AA]">
                            <span className="text-[#F59E0B]">{food.calories}kcal</span>
                            <span className="text-red-400">P:{food.protein}g</span>
                            <span className="text-blue-400">C:{food.carbs}g</span>
                            <span className="text-yellow-400">G:{food.fat}g</span>
                          </div>
                        ) : (
                          <div className="text-xs text-[#71717A] mt-1 italic">Nutrientes pendentes</div>
                        )}
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => handleRemoveFood(idx)}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  ))}
                  
                  {/* Batch Calculate Button */}
                  <Button 
                    onClick={handleEstimateFoodsBatch} 
                    disabled={estimatingFood || mealForm.foods.length === 0}
                    className="w-full bg-gradient-to-r from-[#A855F7] to-[#00F0FF] hover:opacity-90 text-white"
                  >
                    {estimatingFood ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Calculando nutrientes de {mealForm.foods.length} alimento(s)...</>
                    ) : (
                      <><Sparkles className="w-4 h-4 mr-2" /> Calcular Nutrientes de Toda Refeição com IA</>
                    )}
                  </Button>

                  {mealForm.foods.every(f => f.estimated) && mealForm.foods.length > 0 && (
                    <div className="bg-[#121212] border border-green-500/30 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="w-4 h-4 text-green-400" />
                        <span className="text-xs text-green-400 font-medium uppercase">Totais da Refeição</span>
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <div>
                          <span className="text-lg font-bold text-[#F59E0B]">{mealForm.foods.reduce((s, f) => s + (f.calories || 0), 0)}</span>
                          <span className="text-[10px] text-[#52525B] block">kcal</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-red-400">{mealForm.foods.reduce((s, f) => s + (f.protein || 0), 0).toFixed(1)}</span>
                          <span className="text-[10px] text-[#52525B] block">Proteína (g)</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-blue-400">{mealForm.foods.reduce((s, f) => s + (f.carbs || 0), 0).toFixed(1)}</span>
                          <span className="text-[10px] text-[#52525B] block">Carboidratos (g)</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-yellow-400">{mealForm.foods.reduce((s, f) => s + (f.fat || 0), 0).toFixed(1)}</span>
                          <span className="text-[10px] text-[#52525B] block">Gordura (g)</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <Button onClick={handleCreateMeal} className="w-full bg-[#007AFF]" disabled={mealForm.foods.length === 0 || !mealForm.foods.every(f => f.estimated || f.calories > 0)}>
                Salvar Refeição
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Recipe Dialog - Outside Tabs so it works from any tab */}
        <Dialog open={showRecipeDialog} onOpenChange={(open) => { setShowRecipeDialog(open); if (!open) setSuggestedRecipe(null); }}>
          <DialogContent className="bg-[#0A0A0A] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ChefHat className="w-5 h-5 text-green-500" />
                Sugestão de Receita com IA
              </DialogTitle>
              <DialogDescription>Diga suas preferências e receba uma receita personalizada</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {!suggestedRecipe ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Tipo de Refeição</Label>
                      <Select value={recipePreferences.meal_type || "any"} onValueChange={(v) => setRecipePreferences({...recipePreferences, meal_type: v === "any" ? "" : v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue placeholder="Qualquer" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="any">Qualquer</SelectItem>
                          <SelectItem value="breakfast">Café da Manhã</SelectItem>
                          <SelectItem value="lunch">Almoço</SelectItem>
                          <SelectItem value="dinner">Jantar</SelectItem>
                          <SelectItem value="snack">Lanche</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Tipo de Dieta</Label>
                      <Select value={recipePreferences.diet_type || "any"} onValueChange={(v) => setRecipePreferences({...recipePreferences, diet_type: v === "any" ? "" : v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue placeholder="Balanceada" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="any">Balanceada</SelectItem>
                          <SelectItem value="high-protein">Alta Proteína</SelectItem>
                          <SelectItem value="low-carb">Low Carb</SelectItem>
                          <SelectItem value="keto">Cetogênica</SelectItem>
                          <SelectItem value="vegetarian">Vegetariana</SelectItem>
                          <SelectItem value="vegan">Vegana</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Culinária</Label>
                      <Select value={recipePreferences.cuisine || "any"} onValueChange={(v) => setRecipePreferences({...recipePreferences, cuisine: v === "any" ? "" : v})}>
                        <SelectTrigger className="bg-[#121212] border-[#27272A]"><SelectValue placeholder="Qualquer" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="any">Qualquer</SelectItem>
                          <SelectItem value="brasileira">Brasileira</SelectItem>
                          <SelectItem value="italiana">Italiana</SelectItem>
                          <SelectItem value="japonesa">Japonesa</SelectItem>
                          <SelectItem value="mexicana">Mexicana</SelectItem>
                          <SelectItem value="fitness">Fitness</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Tempo Máximo (min)</Label>
                      <Input type="number" value={recipePreferences.max_prep_time_minutes} onChange={(e) => setRecipePreferences({...recipePreferences, max_prep_time_minutes: Number(e.target.value)})} className="bg-[#121212] border-[#27272A]" />
                    </div>
                  </div>
                  <Button onClick={handleSuggestRecipe} className="w-full bg-green-600 hover:bg-green-700" disabled={generatingRecipe}>
                    {generatingRecipe ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Gerando Receita...</> : <><Sparkles className="w-4 h-4 mr-2" />Gerar Receita</>}
                  </Button>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="bg-[#121212] p-4 rounded-lg">
                    <h3 className="text-xl font-bold text-[#00F0FF] mb-2">{suggestedRecipe.name}</h3>
                    <p className="text-[#A1A1AA] mb-4">{suggestedRecipe.description}</p>
                    <div className="grid grid-cols-4 gap-2 mb-4">
                      <div className="text-center p-2 bg-[#0A0A0A] rounded"><Flame className="w-4 h-4 mx-auto text-orange-500" /><span className="text-sm">{suggestedRecipe.calories_per_serving} kcal</span></div>
                      <div className="text-center p-2 bg-[#0A0A0A] rounded"><Dumbbell className="w-4 h-4 mx-auto text-red-500" /><span className="text-sm">{suggestedRecipe.protein_per_serving}g P</span></div>
                      <div className="text-center p-2 bg-[#0A0A0A] rounded"><Zap className="w-4 h-4 mx-auto text-yellow-500" /><span className="text-sm">{suggestedRecipe.carbs_per_serving}g C</span></div>
                      <div className="text-center p-2 bg-[#0A0A0A] rounded"><Droplet className="w-4 h-4 mx-auto text-purple-500" /><span className="text-sm">{suggestedRecipe.fat_per_serving}g G</span></div>
                    </div>
                    <div className="mb-4"><h4 className="font-medium mb-2">Ingredientes</h4><ul className="list-disc list-inside space-y-1 text-[#A1A1AA]">{suggestedRecipe.ingredients?.map((ing, idx) => <li key={idx}>{ing.quantity} {ing.unit} de {ing.name}</li>)}</ul></div>
                    <div className="mb-4"><h4 className="font-medium mb-2">Modo de Preparo</h4><ol className="list-decimal list-inside space-y-2 text-[#A1A1AA]">{suggestedRecipe.instructions?.map((step, idx) => <li key={idx}>{step}</li>)}</ol></div>
                    {suggestedRecipe.tips && <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3"><h4 className="font-medium text-green-400 mb-1">💡 Dica</h4><p className="text-sm text-[#A1A1AA]">{typeof suggestedRecipe.tips === 'string' ? suggestedRecipe.tips : JSON.stringify(suggestedRecipe.tips)}</p></div>}
                  </div>
                  <Button onClick={() => setSuggestedRecipe(null)} variant="outline" className="w-full">Gerar Nova Receita</Button>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

      </main>
      <MobileNav user={user} />
    </div>
  );
}

