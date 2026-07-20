import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { getLocalDateStr, getLocalMonthStr } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DollarSign, Plus, TrendingUp, TrendingDown, AlertCircle, Trash2, CreditCard as CreditCardIcon, Calendar, Repeat, Lightbulb, ChevronRight, ChevronLeft, Edit2, CheckSquare, Square, MessageSquare, Send, Loader2, Bot, User, ArrowUpRight, ArrowDownRight, Wallet } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, LineChart, Line, Legend, AreaChart, Area } from 'recharts';
import axios from "axios";
import { toast } from "sonner";

import ExportButtons from "@/components/ExportButtons";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = ['#007AFF', '#39FF14', '#FF9500', '#FF3B30', '#00F0FF', '#FFD700', '#FF00FF', '#A855F7', '#10B981'];

export default function Finance() {
  const [user, setUser] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [creditCards, setCreditCards] = useState([]);
  const [stats, setStats] = useState(null);
  const [openTransaction, setOpenTransaction] = useState(false);
  const [openBudget, setOpenBudget] = useState(false);
  const [openCard, setOpenCard] = useState(false);
  const [openCharge, setOpenCharge] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  
  // Projection states
  const [projections, setProjections] = useState([]);
  const [projectionSummary, setProjectionSummary] = useState(null);
  const [projectionInsights, setProjectionInsights] = useState(null);
  const [openProjection, setOpenProjection] = useState(false);
  const [openEditProjection, setOpenEditProjection] = useState(false);
  const [selectedProjection, setSelectedProjection] = useState(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [isMobile, setIsMobile] = useState(typeof window !== 'undefined' ? window.innerWidth < 640 : false);

  // Monthly bills
  const [monthlyBills, setMonthlyBills] = useState(null);
  const [billsMonth, setBillsMonth] = useState(() => getLocalMonthStr());
  const [openAddBill, setOpenAddBill] = useState(false);
  const [newBill, setNewBill] = useState({ description: "", amount: "", category: "outros" });

  // Finance chat
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [financeTrend, setFinanceTrend] = useState(null);
  const [projectionMonth, setProjectionMonth] = useState(() => {
    const next = new Date();
    next.setMonth(next.getMonth() + 1);
    return getLocalMonthStr(next);
  });
  
  const [newTransaction, setNewTransaction] = useState({
    type: "expense",
    amount: "",
    category: "alimentação",
    description: "",
    date: getLocalDateStr()
  });
  
  const [newBudget, setNewBudget] = useState({
    category: "alimentação",
    limit: "",
    month: getLocalMonthStr(),
    budget_type: "fixed",
    percentage: ""
  });
  
  const [newCard, setNewCard] = useState({
    name: "",
    limit: "",
    closing_day: "",
    due_day: ""
  });
  
  const [newCharge, setNewCharge] = useState({
    amount: "",
    description: "",
    category: "alimentação",
    payment_type: "vista",
    installments: 2,
    start_month: "current"  // "current" ou "next"
  });
  
  const [newProjection, setNewProjection] = useState({
    description: "",
    amount: "",
    category: "alimentação",
    month: "",
    is_fixed: false,
    repeat_count: 1
  });
  
  const [editProjectionData, setEditProjectionData] = useState({
    amount: "",
    description: ""
  });
  
  const [selectedMonth, setSelectedMonth] = useState(getLocalMonthStr());
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 15;

  // Dynamic categories
  const [categories, setCategories] = useState(["alimentação", "transporte", "moradia", "saúde", "educação", "lazer", "investimentos", "salário", "freelance", "outros"]);
  const [allCategoriesData, setAllCategoriesData] = useState([]);
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryLoading, setCategoryLoading] = useState(false);

  const fetchCategories = async () => {
    try {
      const res = await axios.get(`${API}/finance/categories`, { withCredentials: true });
      const cats = res.data.categories || [];
      setAllCategoriesData(cats);
      setCategories(cats.map(c => c.name));
    } catch {}
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) return;
    setCategoryLoading(true);
    try {
      await axios.post(`${API}/finance/categories`, { name: newCategoryName.trim() }, { withCredentials: true });
      toast.success(`Categoria "${newCategoryName.trim()}" criada!`);
      setNewCategoryName("");
      fetchCategories();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar categoria");
    } finally {
      setCategoryLoading(false);
    }
  };

  const handleDeleteCategory = async (catName) => {
    try {
      await axios.delete(`${API}/finance/categories/${encodeURIComponent(catName)}`, { withCredentials: true });
      toast.success(`Categoria "${catName}" removida`);
      fetchCategories();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao remover categoria");
    }
  };

  useEffect(() => {
    fetchUser();
    fetchTransactions();
    fetchBudgets();
    fetchStats();
    fetchCreditCards();
    fetchFinanceTrend();
    fetchCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMonth]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    fetchProjections();
    fetchProjectionSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectionMonth]);

  const fetchUser = async () => {
    try {
      const res = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(res.data);
    } catch (error) {
      toast.error("Erro ao carregar usuário");
    }
  };

  const fetchTransactions = async () => {
    try {
      const res = await axios.get(`${API}/transactions?month=${selectedMonth}`, { withCredentials: true });
      setTransactions(Array.isArray(res.data) ? res.data : []);
      setCurrentPage(1);
    } catch (error) {
      console.error("Erro ao carregar transações");
    }
  };

  const fetchBudgets = async () => {
    try {
      const res = await axios.get(`${API}/budgets?month=${selectedMonth}`, { withCredentials: true });
      setBudgets(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error("Erro ao carregar orçamentos");
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/finance/stats?month=${selectedMonth}`, { withCredentials: true });
      setStats(res.data);
    } catch (error) {
      console.error("Erro ao carregar estatísticas");
    }
  };

  const fetchFinanceTrend = async () => {
    try {
      const res = await axios.get(`${API}/finance/trend`, { withCredentials: true });
      setFinanceTrend(res.data);
    } catch (error) {
      console.error("Erro ao carregar tendência");
    }
  };

  const fetchCreditCards = async () => {
    try {
      const res = await axios.get(`${API}/credit-cards`, { withCredentials: true });
      setCreditCards(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error("Erro ao carregar cartões");
    }
  };

  const fetchProjections = async () => {
    try {
      const res = await axios.get(`${API}/projections?month=${projectionMonth}`, { withCredentials: true });
      setProjections(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error("Erro ao carregar projeções");
    }
  };

  const fetchProjectionSummary = async () => {
    try {
      const res = await axios.get(`${API}/projections/summary?month=${projectionMonth}`, { withCredentials: true });
      setProjectionSummary(res.data);
    } catch (error) {
      console.error("Erro ao carregar resumo");
    }
  };

  const fetchProjectionInsights = async () => {
    setLoadingInsights(true);
    try {
      const res = await axios.post(`${API}/projections/insights?month=${projectionMonth}`, {}, { withCredentials: true });
      setProjectionInsights(res.data);
    } catch (error) {
      toast.error("Erro ao gerar insights");
    } finally {
      setLoadingInsights(false);
    }
  };


  const fetchMonthlyBills = async (month) => {
    try {
      const res = await axios.get(`${API}/finance/monthly-bills?month=${month || billsMonth}`, { withCredentials: true });
      setMonthlyBills(res.data);
    } catch { setMonthlyBills({ bills: [], total: 0, total_paid: 0, total_pending: 0 }); }
  };

  const handleToggleBill = async (billId) => {
    try {
      await axios.patch(`${API}/finance/monthly-bills/${billId}/toggle`, {}, { withCredentials: true });
      fetchMonthlyBills();
      fetchStats();
      fetchTransactions();
    } catch { toast.error("Erro ao atualizar conta"); }
  };

  const handleAddBill = async () => {
    if (!newBill.description || !newBill.amount) { toast.error("Preencha todos os campos"); return; }
    try {
      await axios.post(`${API}/finance/monthly-bills`, { ...newBill, amount: parseFloat(newBill.amount), month: billsMonth }, { withCredentials: true });
      toast.success("Conta adicionada!");
      setNewBill({ description: "", amount: "", category: "outros" });
      setOpenAddBill(false);
      fetchMonthlyBills();
    } catch { toast.error("Erro ao adicionar conta"); }
  };

  const handleDeleteBill = async (billId) => {
    try {
      await axios.delete(`${API}/finance/monthly-bills/${billId}`, { withCredentials: true });
      fetchMonthlyBills();
    } catch { toast.error("Erro ao remover conta"); }
  };

  const handleSendFinanceChat = async (e) => {
    e?.preventDefault();
    if (!chatInput.trim()) return;
    setChatLoading(true);
    const userMsg = { role: "user", content: chatInput, message_id: `temp_${Date.now()}` };
    setChatMessages(prev => [...prev, userMsg]);
    const text = chatInput;
    setChatInput("");
    try {
      const res = await axios.post(`${API}/chat/send`, { content: text, context: "financial" }, { withCredentials: true });
      setChatMessages(prev => [...prev, { role: "assistant", content: res.data.ai_message?.content || res.data.content || "Sem resposta", message_id: res.data.ai_message?.message_id || `ai_${Date.now()}` }]);
    } catch { setChatMessages(prev => [...prev, { role: "assistant", content: "Erro ao processar. Tente novamente.", message_id: `err_${Date.now()}` }]); }
    finally { setChatLoading(false); }
  };


  const handleCreateTransaction = async () => {
    if (!newTransaction.amount || parseFloat(newTransaction.amount) <= 0) {
      toast.error("Valor inválido");
      return;
    }
    try {
      await axios.post(`${API}/transactions`, {
        ...newTransaction,
        amount: parseFloat(newTransaction.amount)
      }, { withCredentials: true });
      toast.success("Transação registrada!");
      setNewTransaction({
        type: "expense",
        amount: "",
        category: "alimentação",
        description: "",
        date: getLocalDateStr()
      });
      setOpenTransaction(false);
      fetchTransactions();
      fetchBudgets();
      fetchStats();
    } catch (error) {
      toast.error("Erro ao registrar transação");
    }
  };

  const handleCreateBudget = async () => {
    if (newBudget.budget_type === "fixed" && (!newBudget.limit || parseFloat(newBudget.limit) <= 0)) {
      toast.error("Valor inválido");
      return;
    }
    if (newBudget.budget_type === "percentage" && (!newBudget.percentage || parseFloat(newBudget.percentage) <= 0)) {
      toast.error("Percentual inválido");
      return;
    }
    try {
      const budgetData = {
        category: newBudget.category,
        month: newBudget.month,
        budget_type: newBudget.budget_type,
        limit: newBudget.budget_type === "fixed" ? parseFloat(newBudget.limit) : 0,
        percentage: newBudget.budget_type === "percentage" ? parseFloat(newBudget.percentage) : null
      };
      await axios.post(`${API}/budgets`, budgetData, { withCredentials: true });
      toast.success("Orçamento criado!");
      setNewBudget({
        category: "alimentação",
        limit: "",
        month: getLocalMonthStr(),
        budget_type: "fixed",
        percentage: ""
      });
      setOpenBudget(false);
      fetchBudgets();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar orçamento");
    }
  };

  const handleCreateCard = async () => {
    if (!newCard.name || !newCard.limit || !newCard.closing_day || !newCard.due_day) {
      toast.error("Preencha todos os campos");
      return;
    }
    try {
      await axios.post(`${API}/credit-cards`, {
        ...newCard,
        limit: parseFloat(newCard.limit),
        closing_day: parseInt(newCard.closing_day),
        due_day: parseInt(newCard.due_day)
      }, { withCredentials: true });
      toast.success("Cartão cadastrado!");
      setNewCard({ name: "", limit: "", closing_day: "", due_day: "" });
      setOpenCard(false);
      fetchCreditCards();
    } catch (error) {
      toast.error("Erro ao cadastrar cartão");
    }
  };

  const handleChargeCard = async () => {
    if (!newCharge.amount || parseFloat(newCharge.amount) <= 0) {
      toast.error("Valor inválido");
      return;
    }
    try {
      const chargeData = {
        amount: parseFloat(newCharge.amount),
        description: newCharge.description,
        category: newCharge.category,
        payment_type: newCharge.payment_type,
        installments: newCharge.payment_type === "parcelado" ? parseInt(newCharge.installments) : 1,
        start_month: newCharge.start_month
      };
      
      const res = await axios.post(`${API}/credit-cards/${selectedCard}/charge`, chargeData, { withCredentials: true });
      
      if (newCharge.payment_type === "parcelado") {
        toast.success(`Compra parcelada em ${chargeData.installments}x de R$ ${(res.data.installment_amount ?? 0).toFixed(2)} lançada!`);
      } else {
        toast.success("Compra à vista lançada no cartão!");
      }
      
      setNewCharge({ amount: "", description: "", category: "alimentação", payment_type: "vista", installments: 2, start_month: "current" });
      setOpenCharge(false);
      fetchTransactions();
      fetchStats();
      fetchProjections();
      fetchProjectionSummary();
    } catch (error) {
      toast.error("Erro ao lançar compra");
    }
  };

  const handleCreateProjection = async () => {
    if (!newProjection.amount || parseFloat(newProjection.amount) <= 0) {
      toast.error("Valor inválido");
      return;
    }
    if (!newProjection.description) {
      toast.error("Descrição obrigatória");
      return;
    }
    try {
      await axios.post(`${API}/projections`, {
        ...newProjection,
        amount: parseFloat(newProjection.amount),
        month: newProjection.month || projectionMonth,
        repeat_count: newProjection.is_fixed ? null : parseInt(newProjection.repeat_count) || 1
      }, { withCredentials: true });
      
      toast.success("Projeção criada!");
      setNewProjection({
        description: "",
        amount: "",
        category: "alimentação",
        month: "",
        is_fixed: false,
        repeat_count: 1
      });
      setOpenProjection(false);
      fetchProjections();
      fetchProjectionSummary();
    } catch (error) {
      toast.error("Erro ao criar projeção");
    }
  };

  const handleUpdateProjection = async () => {
    if (!selectedProjection) return;
    
    try {
      const params = new URLSearchParams();
      if (editProjectionData.amount) params.append('amount', editProjectionData.amount);
      if (editProjectionData.description) params.append('description', editProjectionData.description);
      
      await axios.patch(`${API}/projections/${selectedProjection.projection_id}?${params.toString()}`, {}, { withCredentials: true });
      toast.success("Projeção atualizada!");
      setOpenEditProjection(false);
      setSelectedProjection(null);
      fetchProjections();
      fetchProjectionSummary();
    } catch (error) {
      toast.error("Erro ao atualizar projeção");
    }
  };

  const handleDeleteProjection = async (projectionId) => {
    try {
      await axios.delete(`${API}/projections/${projectionId}`, { withCredentials: true });
      toast.success("Projeção removida");
      fetchProjections();
      fetchProjectionSummary();
    } catch (error) {
      toast.error("Erro ao remover projeção");
    }
  };

  const handleDeleteTransaction = async (id) => {
    try {
      await axios.delete(`${API}/transactions/${id}`, { withCredentials: true });
      toast.success("Transação deletada");
      fetchTransactions();
      fetchStats();
    } catch (error) {
      toast.error("Erro ao deletar transação");
    }
  };

  const income = transactions.filter(t => t.type === 'income').reduce((sum, t) => sum + t.amount, 0);
  const expenses = transactions.filter(t => t.type === 'expense').reduce((sum, t) => sum + t.amount, 0);
  const balance = income - expenses;

  const chartData = stats && stats.expense_by_category ? Object.entries(stats.expense_by_category).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: value
  })) : [];

  const projectionChartData = projectionSummary?.categories_totals ? 
    Object.entries(projectionSummary.categories_totals).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value: value
    })) : [];

  // Generate future months for selection
  const futureMonths = [];
  for (let i = 1; i <= 12; i++) {
    const date = new Date();
    date.setMonth(date.getMonth() + i);
    futureMonths.push(getLocalMonthStr(date));
  }

  const getMonthLabel = (monthStr) => {
    const [year, month] = monthStr.split('-');
    const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    return `${months[parseInt(month) - 1]} ${year}`;
  };

  return (
    <div className="flex min-h-screen bg-[#050505]">
      <Sidebar user={user} />
      <div className="flex-1 ml-0 md:ml-64 p-4 md:p-8 pb-24 md:pb-8 pt-[72px] md:pt-8">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <h1 className="font-heading text-3xl md:text-4xl mb-2">FINANÇAS</h1>
                <p className="text-[#A1A1AA]">Controle total do seu dinheiro</p>
              </div>
              <ExportButtons module="finance" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[#A1A1AA] uppercase text-xs tracking-wider">Receitas</span>
                <TrendingUp className="w-5 h-5 text-[#39FF14]" />
              </div>
              <p className="font-data text-2xl md:text-3xl text-[#39FF14]">R$ {(income ?? 0).toFixed(2)}</p>
            </Card>

            <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[#A1A1AA] uppercase text-xs tracking-wider">Despesas</span>
                <TrendingDown className="w-5 h-5 text-[#FF3B30]" />
              </div>
              <p className="font-data text-2xl md:text-3xl text-[#FF3B30]">R$ {(expenses ?? 0).toFixed(2)}</p>
            </Card>

            <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[#A1A1AA] uppercase text-xs tracking-wider">Saldo</span>
                <DollarSign className="w-5 h-5 text-[#007AFF]" />
              </div>
              <p className={`font-data text-2xl md:text-3xl ${(balance ?? 0) >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                R$ {(balance ?? 0).toFixed(2)}
              </p>
            </Card>
          </div>

          {chartData.length > 0 && (
            <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6 mb-8">
              <h3 className="font-heading text-xl mb-4 uppercase">Gastos por Categoria</h3>
              <ResponsiveContainer width="100%" height={isMobile ? 250 : 350}>
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={isMobile ? 65 : 120}
                    label={isMobile ? (entry) => `${entry.name}` : (entry) => `${entry.name}: R$ ${(entry.value ?? 0).toFixed(0)}`}
                    labelLine={!isMobile}
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `R$ ${(value ?? 0).toFixed(2)}`} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Finance Trend - Last 6 Months */}
          {financeTrend && financeTrend.trend && financeTrend.trend.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
              <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6 lg:col-span-2">
                <h3 className="font-heading text-lg mb-4 uppercase flex items-center gap-2"><TrendingUp className="w-4 h-4 text-[#007AFF]" />Evolução Financeira (6 meses)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={financeTrend.trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                    <XAxis dataKey="month" tick={{ fill: '#71717A', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#71717A', fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A', color: '#fff' }} formatter={(v) => `R$ ${v.toFixed(2)}`} />
                    <Area type="monotone" dataKey="receitas" stroke="#39FF14" fill="#39FF1420" name="Receitas" />
                    <Area type="monotone" dataKey="despesas" stroke="#FF3B30" fill="#FF3B3020" name="Despesas" />
                    <Line type="monotone" dataKey="saldo" stroke="#007AFF" strokeWidth={2} name="Saldo" dot={false} />
                    <Legend />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
              <Card className="bg-[#0A0A0A] border-[#27272A] p-4 md:p-6">
                <h3 className="font-heading text-lg mb-4 uppercase">Resumo 6 Meses</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[#A1A1AA] text-xs">Taxa de Economia</span>
                    <span className={`font-data text-lg ${financeTrend.summary.savings_rate >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                      {financeTrend.summary.savings_rate}%
                    </span>
                  </div>
                  <div className="w-full bg-[#27272A] rounded-full h-2">
                    <div className="h-2 rounded-full bg-gradient-to-r from-[#39FF14] to-[#007AFF]" style={{ width: `${Math.min(Math.max(financeTrend.summary.savings_rate, 0), 100)}%` }}></div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#A1A1AA] text-xs">Receitas (6m)</span>
                    <span className="font-data text-sm text-[#39FF14]">R$ {financeTrend.summary.total_income_6m.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#A1A1AA] text-xs">Despesas (6m)</span>
                    <span className="font-data text-sm text-[#FF3B30]">R$ {financeTrend.summary.total_expense_6m.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#A1A1AA] text-xs">Média Mensal Despesas</span>
                    <span className="font-data text-sm text-white">R$ {financeTrend.summary.avg_monthly_expense.toFixed(2)}</span>
                  </div>
                  {financeTrend.summary.best_month && (
                    <div className="flex items-center justify-between">
                      <span className="text-[#A1A1AA] text-xs">Melhor Mês</span>
                      <span className="font-data text-sm text-[#39FF14]">{financeTrend.summary.best_month}</span>
                    </div>
                  )}
                  {financeTrend.trend.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[#27272A]">
                      <p className="text-[10px] text-[#52525B] uppercase tracking-wider mb-2">Economia por Mês</p>
                      <div className="space-y-1">
                        {financeTrend.trend.map((m, i) => (
                          <div key={i} className="flex items-center gap-2">
                            <span className="text-[10px] text-[#71717A] w-12">{m.month}</span>
                            <div className="flex-1 bg-[#27272A] rounded-full h-1.5">
                              <div className={`h-1.5 rounded-full ${m.economia >= 0 ? 'bg-[#39FF14]' : 'bg-[#FF3B30]'}`} style={{ width: `${Math.min(Math.abs(m.economia), 100)}%` }}></div>
                            </div>
                            <span className={`text-[10px] font-data ${m.economia >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>{m.economia}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          )}

          <div className="mb-6">
            <Input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="bg-[#0A0A0A] border-[#27272A] text-white font-mono max-w-xs"
            />
          </div>

          <Tabs defaultValue="transactions" className="w-full">
            <TabsList className="bg-[#0A0A0A] border-[#27272A] overflow-x-auto flex-nowrap w-full justify-start md:justify-center">
              <TabsTrigger value="transactions">Transações</TabsTrigger>
              <TabsTrigger value="budgets">Orçamentos</TabsTrigger>
              <TabsTrigger value="cards">Cartões</TabsTrigger>
              <TabsTrigger value="bills" onClick={() => fetchMonthlyBills()}>Contas do Mês</TabsTrigger>
              <TabsTrigger value="projections">Projeção</TabsTrigger>
              <TabsTrigger value="finance_chat">Chat Financeiro</TabsTrigger>
              <TabsTrigger value="categories">Categorias</TabsTrigger>
            </TabsList>

            <TabsContent value="transactions" className="mt-6">
              <div className="flex justify-end mb-4">
                <Dialog open={openTransaction} onOpenChange={setOpenTransaction}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">
                      <Plus className="w-4 h-4 mr-2" />
                      Nova Transação
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="font-heading text-2xl">NOVA TRANSAÇÃO</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div>
                        <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Tipo</Label>
                        <div className="flex gap-2">
                          {[{value: 'income', label: 'Receita'}, {value: 'expense', label: 'Despesa'}].map((type) => (
                            <button
                              key={type.value}
                              onClick={() => setNewTransaction({...newTransaction, type: type.value})}
                              className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                                newTransaction.type === type.value ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                              }`}
                            >
                              {type.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <Label>Valor</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={newTransaction.amount}
                          onChange={(e) => setNewTransaction({...newTransaction, amount: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div>
                        <Label>Categoria</Label>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          {categories.map(cat => (
                            <button
                              key={cat}
                              onClick={() => setNewTransaction({...newTransaction, category: cat})}
                              className={`py-2 px-3 rounded-sm text-xs uppercase transition-colors ${
                                newTransaction.category === cat ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                              }`}
                            >
                              {cat}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <Label>Descrição</Label>
                        <Input
                          value={newTransaction.description}
                          onChange={(e) => setNewTransaction({...newTransaction, description: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div>
                        <Label>Data</Label>
                        <Input
                          type="date"
                          value={newTransaction.date}
                          onChange={(e) => setNewTransaction({...newTransaction, date: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <Button onClick={handleCreateTransaction} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                        Criar
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="space-y-3">
                {transactions.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <p className="text-[#A1A1AA]">Nenhuma transação neste período</p>
                  </Card>
                ) : (
                  <>
                    {transactions
                      .slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
                      .map((t) => (
                      <Card key={t.transaction_id} className="bg-[#0A0A0A] border-[#27272A] p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4 flex-1">
                            <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${
                              t.type === 'income' ? 'bg-[#39FF14]/20' : 'bg-[#FF3B30]/20'
                            }`}>
                              {t.type === 'income' ? <TrendingUp className="w-5 h-5 text-[#39FF14]" /> : <TrendingDown className="w-5 h-5 text-[#FF3B30]" />}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-1">
                                <span className="font-medium">{t.category}</span>
                                <span className="text-xs text-[#A1A1AA]">{t.date}</span>
                              </div>
                              {t.description && <p className="text-sm text-[#A1A1AA]">{t.description}</p>}
                            </div>
                            <div className={`font-data text-xl ${t.type === 'income' ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                              {t.type === 'income' ? '+' : '-'}R$ {(t.amount ?? 0).toFixed(2)}
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => handleDeleteTransaction(t.transaction_id)}>
                              <Trash2 className="w-4 h-4 text-[#52525B] hover:text-[#FF3B30]" />
                            </Button>
                          </div>
                        </div>
                      </Card>
                    ))}
                    
                    {/* Pagination Controls */}
                    {transactions.length > ITEMS_PER_PAGE && (
                      <div className="flex items-center justify-between pt-4">
                        <p className="text-sm text-[#A1A1AA]">
                          Mostrando {((currentPage - 1) * ITEMS_PER_PAGE) + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, transactions.length)} de {transactions.length} transações
                        </p>
                        <div className="flex items-center space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1}
                            className="bg-[#121212] border-[#27272A] text-[#A1A1AA] hover:bg-[#1A1A1A] disabled:opacity-30"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </Button>
                          {Array.from({ length: Math.ceil(transactions.length / ITEMS_PER_PAGE) }, (_, i) => i + 1)
                            .filter(page => {
                              const totalPages = Math.ceil(transactions.length / ITEMS_PER_PAGE);
                              if (totalPages <= 7) return true;
                              if (page === 1 || page === totalPages) return true;
                              if (Math.abs(page - currentPage) <= 1) return true;
                              return false;
                            })
                            .map((page, idx, arr) => {
                              const elements = [];
                              if (idx > 0 && page - arr[idx - 1] > 1) {
                                elements.push(
                                  <span key={`dots-${page}`} className="text-[#52525B] px-1">...</span>
                                );
                              }
                              elements.push(
                                <Button
                                  key={page}
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setCurrentPage(page)}
                                  className={`min-w-[36px] ${
                                    currentPage === page
                                      ? 'bg-[#007AFF] border-[#007AFF] text-white hover:bg-[#0062CC]'
                                      : 'bg-[#121212] border-[#27272A] text-[#A1A1AA] hover:bg-[#1A1A1A]'
                                  }`}
                                >
                                  {page}
                                </Button>
                              );
                              return elements;
                            })}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.min(Math.ceil(transactions.length / ITEMS_PER_PAGE), p + 1))}
                            disabled={currentPage >= Math.ceil(transactions.length / ITEMS_PER_PAGE)}
                            className="bg-[#121212] border-[#27272A] text-[#A1A1AA] hover:bg-[#1A1A1A] disabled:opacity-30"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </TabsContent>

            <TabsContent value="budgets" className="mt-6">
              <div className="flex justify-end mb-4">
                <Dialog open={openBudget} onOpenChange={setOpenBudget}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">
                      <Plus className="w-4 h-4 mr-2" />
                      Novo Orçamento
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="font-heading text-2xl">NOVO ORÇAMENTO</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div>
                        <Label>Categoria</Label>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          {categories.map(cat => (
                            <button
                              key={cat}
                              onClick={() => setNewBudget({...newBudget, category: cat})}
                              className={`py-2 px-3 rounded-sm text-xs uppercase transition-colors ${
                                newBudget.category === cat ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                              }`}
                            >
                              {cat}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <Label>Tipo</Label>
                        <div className="flex gap-2 mt-2">
                          {[{value: 'fixed', label: 'Valor Fixo'}, {value: 'percentage', label: '%'}].map((type) => (
                            <button
                              key={type.value}
                              onClick={() => setNewBudget({...newBudget, budget_type: type.value})}
                              className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                                newBudget.budget_type === type.value ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                              }`}
                            >
                              {type.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {newBudget.budget_type === 'fixed' ? (
                        <div>
                          <Label>Limite (R$)</Label>
                          <Input
                            type="number"
                            value={newBudget.limit}
                            onChange={(e) => setNewBudget({...newBudget, limit: e.target.value})}
                            className="bg-[#121212] border-[#27272A] text-white"
                          />
                        </div>
                      ) : (
                        <div>
                          <Label>% da Renda</Label>
                          <Input
                            type="number"
                            value={newBudget.percentage}
                            onChange={(e) => setNewBudget({...newBudget, percentage: e.target.value})}
                            className="bg-[#121212] border-[#27272A] text-white"
                          />
                        </div>
                      )}
                      <Button onClick={handleCreateBudget} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                        Criar
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {budgets.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center col-span-full">
                    <p className="text-[#A1A1AA]">Nenhum orçamento definido</p>
                  </Card>
                ) : (
                  budgets.map((budget) => {
                    const percentage = (budget.spent / budget.limit) * 100;
                    const isOver = percentage > 100;
                    return (
                      <Card key={budget.budget_id} className={`bg-[#0A0A0A] border-[#27272A] p-6 ${isOver ? 'border-[#FF3B30]' : ''}`}>
                        {isOver && (
                          <div className="flex items-center space-x-2 mb-3 text-[#FF3B30]">
                            <AlertCircle className="w-5 h-5" />
                            <span className="text-sm uppercase">Estourado</span>
                          </div>
                        )}
                        <h3 className="font-heading text-xl mb-4">{budget.category.toUpperCase()}</h3>
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-[#A1A1AA]">Gasto</span>
                            <span>R$ {(budget.spent ?? 0).toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-[#A1A1AA]">Limite</span>
                            <span>R$ {(budget.limit ?? 0).toFixed(2)}</span>
                          </div>
                          <div className="h-2 bg-[#27272A] rounded-full overflow-hidden mt-3">
                            <div className={`h-full ${isOver ? 'bg-[#FF3B30]' : 'bg-[#007AFF]'}`} style={{ width: `${Math.min(percentage, 100)}%` }} />
                          </div>
                        </div>
                      </Card>
                    );
                  })
                )}
              </div>
            </TabsContent>

            <TabsContent value="cards" className="mt-6">
              <div className="flex justify-end mb-4 space-x-2">
                <Dialog open={openCard} onOpenChange={setOpenCard}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">
                      <Plus className="w-4 h-4 mr-2" />
                      Novo Cartão
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="font-heading text-2xl">CADASTRAR CARTÃO</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div>
                        <Label>Nome do Cartão</Label>
                        <Input
                          value={newCard.name}
                          onChange={(e) => setNewCard({...newCard, name: e.target.value})}
                          placeholder="Ex: Nubank, Itaú"
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div>
                        <Label>Limite (R$)</Label>
                        <Input
                          type="number"
                          value={newCard.limit}
                          onChange={(e) => setNewCard({...newCard, limit: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Dia Fechamento</Label>
                          <Input
                            type="number"
                            min="1"
                            max="31"
                            value={newCard.closing_day}
                            onChange={(e) => setNewCard({...newCard, closing_day: e.target.value})}
                            className="bg-[#121212] border-[#27272A] text-white"
                          />
                        </div>
                        <div>
                          <Label>Dia Vencimento</Label>
                          <Input
                            type="number"
                            min="1"
                            max="31"
                            value={newCard.due_day}
                            onChange={(e) => setNewCard({...newCard, due_day: e.target.value})}
                            className="bg-[#121212] border-[#27272A] text-white"
                          />
                        </div>
                      </div>
                      <Button onClick={handleCreateCard} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                        Cadastrar
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {creditCards.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center col-span-full">
                    <CreditCardIcon className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhum cartão cadastrado</p>
                  </Card>
                ) : (
                  creditCards.map((card) => (
                    <Card key={card.card_id} className="bg-[#0A0A0A] border-[#27272A] p-6">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="w-12 h-12 bg-[#007AFF]/20 rounded-sm flex items-center justify-center">
                          <CreditCardIcon className="w-6 h-6 text-[#007AFF]" />
                        </div>
                        <div>
                          <h3 className="font-heading text-lg">{card.name}</h3>
                          <p className="text-xs text-[#A1A1AA]">Limite: R$ {(card.limit ?? 0).toFixed(2)}</p>
                        </div>
                      </div>
                      <div className="space-y-2 text-sm mb-4">
                        <div className="flex justify-between">
                          <span className="text-[#A1A1AA]">Fechamento</span>
                          <span>Dia {card.closing_day}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#A1A1AA]">Vencimento</span>
                          <span>Dia {card.due_day}</span>
                        </div>
                      </div>
                      <Dialog open={openCharge && selectedCard === card.card_id} onOpenChange={(open) => {
                        setOpenCharge(open);
                        if (!open) setSelectedCard(null);
                      }}>
                        <DialogTrigger asChild>
                          <Button 
                            onClick={() => setSelectedCard(card.card_id)}
                            className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs"
                          >
                            Lançar Compra
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                          <DialogHeader>
                            <DialogTitle className="font-heading text-xl">LANÇAR NO {card.name.toUpperCase()}</DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4 mt-4">
                            <div>
                              <Label>Valor Total</Label>
                              <Input
                                type="number"
                                step="0.01"
                                value={newCharge.amount}
                                onChange={(e) => setNewCharge({...newCharge, amount: e.target.value})}
                                className="bg-[#121212] border-[#27272A] text-white"
                              />
                            </div>
                            <div>
                              <Label>Descrição</Label>
                              <Input
                                value={newCharge.description}
                                onChange={(e) => setNewCharge({...newCharge, description: e.target.value})}
                                className="bg-[#121212] border-[#27272A] text-white"
                              />
                            </div>
                            <div>
                              <Label>Categoria</Label>
                              <div className="grid grid-cols-2 gap-2 mt-2">
                                {categories.map(cat => (
                                  <button
                                    key={cat}
                                    onClick={() => setNewCharge({...newCharge, category: cat})}
                                    className={`py-2 px-3 rounded-sm text-xs uppercase transition-colors ${
                                      newCharge.category === cat ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                                    }`}
                                  >
                                    {cat}
                                  </button>
                                ))}
                              </div>
                            </div>
                            
                            {/* Payment Type Selection */}
                            <div>
                              <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Forma de Pagamento</Label>
                              <div className="flex gap-2">
                                {[{value: 'vista', label: 'À Vista'}, {value: 'parcelado', label: 'Parcelado'}].map((type) => (
                                  <button
                                    key={type.value}
                                    onClick={() => setNewCharge({...newCharge, payment_type: type.value})}
                                    className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                                      newCharge.payment_type === type.value ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                                    }`}
                                  >
                                    {type.label}
                                  </button>
                                ))}
                              </div>
                            </div>
                            
                            {/* Installments (only show when parcelado) */}
                            {newCharge.payment_type === 'parcelado' && (
                              <>
                                <div>
                                  <Label>Número de Parcelas</Label>
                                  <Input
                                    type="number"
                                    min="2"
                                    max="24"
                                    value={newCharge.installments}
                                    onChange={(e) => setNewCharge({...newCharge, installments: e.target.value})}
                                    className="bg-[#121212] border-[#27272A] text-white"
                                  />
                                  {newCharge.amount && newCharge.installments >= 2 && (
                                    <p className="text-sm text-[#A1A1AA] mt-2">
                                      {newCharge.installments}x de R$ {(parseFloat(newCharge.amount) / parseInt(newCharge.installments)).toFixed(2)}
                                    </p>
                                  )}
                                </div>
                                
                                <div>
                                  <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Primeira Parcela</Label>
                                  <div className="flex gap-2">
                                    <button
                                      onClick={() => setNewCharge({...newCharge, start_month: 'current'})}
                                      className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                                        newCharge.start_month === 'current' ? 'bg-[#22C55E] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                                      }`}
                                    >
                                      Mês Atual
                                    </button>
                                    <button
                                      onClick={() => setNewCharge({...newCharge, start_month: 'next'})}
                                      className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                                        newCharge.start_month === 'next' ? 'bg-[#F59E0B] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                                      }`}
                                    >
                                      Próximo Mês
                                    </button>
                                  </div>
                                  <p className="text-xs text-[#52525B] mt-1">
                                    {newCharge.start_month === 'current' 
                                      ? 'A primeira parcela será cobrada neste mês' 
                                      : 'A primeira parcela será cobrada no próximo mês'}
                                  </p>
                                </div>
                              </>
                            )}
                            
                            <Button onClick={handleChargeCard} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                              Lançar
                            </Button>
                          </div>
                        </DialogContent>
                      </Dialog>
                    </Card>
                  ))
                )}
              </div>
            </TabsContent>

            {/* PROJECTIONS TAB */}
            <TabsContent value="projections" className="mt-6">
              {/* Month Selector */}
              <div className="flex flex-wrap items-center gap-4 mb-6">
                <div className="flex items-center space-x-2">
                  <Calendar className="w-5 h-5 text-[#007AFF]" />
                  <span className="text-[#A1A1AA] uppercase text-xs">Projeção para:</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {futureMonths.slice(0, 6).map((month) => (
                    <button
                      key={month}
                      onClick={() => setProjectionMonth(month)}
                      className={`py-2 px-4 rounded-sm text-xs uppercase transition-colors ${
                        projectionMonth === month ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA] hover:bg-[#1a1a1a]'
                      }`}
                    >
                      {getMonthLabel(month)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Summary Cards */}
              {projectionSummary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[#A1A1AA] uppercase text-xs">Receita Estimada</span>
                      <TrendingUp className="w-4 h-4 text-[#39FF14]" />
                    </div>
                    <p className="font-data text-xl text-[#39FF14]">R$ {(projectionSummary.estimated_income ?? 0).toFixed(2)}</p>
                  </Card>
                  
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[#A1A1AA] uppercase text-xs">Despesas Projetadas</span>
                      <TrendingDown className="w-4 h-4 text-[#FF9500]" />
                    </div>
                    <p className="font-data text-xl text-[#FF9500]">R$ {(projectionSummary.total_projected_expenses ?? 0).toFixed(2)}</p>
                  </Card>
                  
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[#A1A1AA] uppercase text-xs">Saldo Estimado</span>
                      <DollarSign className="w-4 h-4 text-[#007AFF]" />
                    </div>
                    <p className={`font-data text-xl ${(projectionSummary.estimated_balance ?? 0) >= 0 ? 'text-[#39FF14]' : 'text-[#FF3B30]'}`}>
                      R$ {(projectionSummary.estimated_balance ?? 0).toFixed(2)}
                    </p>
                  </Card>
                  
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[#A1A1AA] uppercase text-xs">Parcelas</span>
                      <CreditCardIcon className="w-4 h-4 text-[#00F0FF]" />
                    </div>
                    <p className="font-data text-xl text-[#00F0FF]">R$ {(projectionSummary.installment_expenses ?? 0).toFixed(2)}</p>
                  </Card>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-wrap justify-between items-center mb-4 gap-2">
                <Button 
                  onClick={fetchProjectionInsights}
                  disabled={loadingInsights}
                  className="bg-[#FFD700] hover:bg-[#e6c200] text-black uppercase text-xs tracking-widest"
                >
                  <Lightbulb className="w-4 h-4 mr-2" />
                  {loadingInsights ? 'Gerando...' : 'Gerar Insights com IA'}
                </Button>
                
                <Dialog open={openProjection} onOpenChange={setOpenProjection}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs tracking-widest">
                      <Plus className="w-4 h-4 mr-2" />
                      Nova Projeção
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="font-heading text-2xl">NOVA PROJEÇÃO</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div>
                        <Label>Descrição</Label>
                        <Input
                          value={newProjection.description}
                          onChange={(e) => setNewProjection({...newProjection, description: e.target.value})}
                          placeholder="Ex: Aluguel, Netflix, etc."
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div>
                        <Label>Valor (R$)</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={newProjection.amount}
                          onChange={(e) => setNewProjection({...newProjection, amount: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      <div>
                        <Label>Categoria</Label>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          {categories.map(cat => (
                            <button
                              key={cat}
                              onClick={() => setNewProjection({...newProjection, category: cat})}
                              className={`py-2 px-3 rounded-sm text-xs uppercase transition-colors ${
                                newProjection.category === cat ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                              }`}
                            >
                              {cat}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <Label>Mês Inicial</Label>
                        <Input
                          type="month"
                          value={newProjection.month || projectionMonth}
                          onChange={(e) => setNewProjection({...newProjection, month: e.target.value})}
                          className="bg-[#121212] border-[#27272A] text-white"
                        />
                      </div>
                      
                      {/* Fixed or Repeat */}
                      <div>
                        <Label className="text-[#A1A1AA] uppercase text-xs tracking-wider mb-2 block">Recorrência</Label>
                        <div className="flex gap-2 mb-3">
                          <button
                            onClick={() => setNewProjection({...newProjection, is_fixed: true, repeat_count: 1})}
                            className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors flex items-center justify-center gap-2 ${
                              newProjection.is_fixed ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                            }`}
                          >
                            <Repeat className="w-4 h-4" />
                            Despesa Fixa
                          </button>
                          <button
                            onClick={() => setNewProjection({...newProjection, is_fixed: false})}
                            className={`flex-1 py-2 px-4 rounded-sm uppercase text-xs transition-colors ${
                              !newProjection.is_fixed ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#A1A1AA]'
                            }`}
                          >
                            Temporária
                          </button>
                        </div>
                        
                        {!newProjection.is_fixed && (
                          <div>
                            <Label>Repetir por quantos meses?</Label>
                            <Input
                              type="number"
                              min="1"
                              max="24"
                              value={newProjection.repeat_count}
                              onChange={(e) => setNewProjection({...newProjection, repeat_count: e.target.value})}
                              className="bg-[#121212] border-[#27272A] text-white"
                            />
                          </div>
                        )}
                      </div>
                      
                      <Button onClick={handleCreateProjection} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                        Criar Projeção
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              {/* AI Insights */}
              {projectionInsights && (
                <Card className="bg-[#0A0A0A] border-[#FFD700]/30 p-6 mb-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <Lightbulb className="w-5 h-5 text-[#FFD700]" />
                    <h3 className="font-heading text-lg text-[#FFD700]">INSIGHTS DA IA</h3>
                  </div>
                  <div className="prose prose-invert max-w-none">
                    <p className="text-[#E4E4E7] whitespace-pre-wrap text-sm leading-relaxed">{projectionInsights.insights}</p>
                  </div>
                </Card>
              )}

              {/* Projection Chart */}
              {projectionChartData.length > 0 && (
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6 mb-6">
                  <h3 className="font-heading text-lg mb-4 uppercase">Projeção por Categoria</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={projectionChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                      <XAxis dataKey="name" tick={{ fill: '#A1A1AA', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#A1A1AA', fontSize: 12 }} />
                      <Tooltip 
                        formatter={(value) => `R$ ${(value ?? 0).toFixed(2)}`}
                        contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #27272A' }}
                      />
                      <Bar dataKey="value" fill="#007AFF" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
              )}

              {/* Projections List */}
              <div className="space-y-3">
                {projections.length === 0 ? (
                  <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                    <Calendar className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                    <p className="text-[#A1A1AA]">Nenhuma projeção para {getMonthLabel(projectionMonth)}</p>
                    <p className="text-xs text-[#52525B] mt-2">Adicione compras parceladas ou crie projeções manuais</p>
                  </Card>
                ) : (
                  projections.map((proj) => (
                    <Card key={proj.projection_id} className="bg-[#0A0A0A] border-[#27272A] p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4 flex-1">
                          <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${
                            proj.projection_type === 'installment' ? 'bg-[#00F0FF]/20' : 
                            proj.is_fixed ? 'bg-[#FFD700]/20' : 'bg-[#007AFF]/20'
                          }`}>
                            {proj.projection_type === 'installment' ? (
                              <CreditCardIcon className="w-5 h-5 text-[#00F0FF]" />
                            ) : proj.is_fixed ? (
                              <Repeat className="w-5 h-5 text-[#FFD700]" />
                            ) : (
                              <Calendar className="w-5 h-5 text-[#007AFF]" />
                            )}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-1">
                              <span className="font-medium">{proj.description}</span>
                              {proj.projection_type === 'installment' && (
                                <span className="text-xs bg-[#00F0FF]/20 text-[#00F0FF] px-2 py-0.5 rounded">
                                  Parcela {proj.installment_number}/{proj.total_installments}
                                </span>
                              )}
                              {proj.is_fixed && (
                                <span className="text-xs bg-[#FFD700]/20 text-[#FFD700] px-2 py-0.5 rounded">
                                  Fixa
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-[#A1A1AA]">{proj.category}</p>
                          </div>
                          <div className="font-data text-xl text-[#FF9500]">
                            R$ {(proj.amount ?? 0).toFixed(2)}
                          </div>
                          <div className="flex items-center space-x-1">
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => {
                                setSelectedProjection(proj);
                                setEditProjectionData({ amount: proj.amount.toString(), description: proj.description });
                                setOpenEditProjection(true);
                              }}
                            >
                              <Edit2 className="w-4 h-4 text-[#52525B] hover:text-[#007AFF]" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              onClick={() => handleDeleteProjection(proj.projection_id)}
                            >
                              <Trash2 className="w-4 h-4 text-[#52525B] hover:text-[#FF3B30]" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))
                )}
              </div>

              {/* Edit Projection Dialog */}
              <Dialog open={openEditProjection} onOpenChange={setOpenEditProjection}>
                <DialogContent className="bg-[#0A0A0A] border-[#27272A] text-white max-w-md">
                  <DialogHeader>
                    <DialogTitle className="font-heading text-2xl">EDITAR PROJEÇÃO</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 mt-4">
                    <div>
                      <Label>Descrição</Label>
                      <Input
                        value={editProjectionData.description}
                        onChange={(e) => setEditProjectionData({...editProjectionData, description: e.target.value})}
                        className="bg-[#121212] border-[#27272A] text-white"
                      />
                    </div>
                    <div>
                      <Label>Valor (R$)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={editProjectionData.amount}
                        onChange={(e) => setEditProjectionData({...editProjectionData, amount: e.target.value})}
                        className="bg-[#121212] border-[#27272A] text-white"
                      />
                    </div>
                    <Button onClick={handleUpdateProjection} className="w-full bg-[#007AFF] hover:bg-[#0062CC] uppercase text-xs">
                      Salvar Alterações
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </TabsContent>

            {/* ===== CONTAS DO MÊS TAB ===== */}
            <TabsContent value="bills" className="mt-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { const d = new Date(billsMonth + "-01"); d.setMonth(d.getMonth() - 1); const m = getLocalMonthStr(d); setBillsMonth(m); fetchMonthlyBills(m); }}><ChevronLeft className="w-4 h-4" /></Button>
                  <span className="text-sm font-medium min-w-[100px] text-center">{new Date(billsMonth + "-01").toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}</span>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { const d = new Date(billsMonth + "-01"); d.setMonth(d.getMonth() + 1); const m = getLocalMonthStr(d); setBillsMonth(m); fetchMonthlyBills(m); }}><ChevronRight className="w-4 h-4" /></Button>
                </div>
                <Dialog open={openAddBill} onOpenChange={setOpenAddBill}>
                  <Button onClick={() => setOpenAddBill(true)} size="sm" className="bg-[#007AFF] text-xs"><Plus className="w-3 h-3 mr-1" />Adicionar Conta</Button>
                  <DialogContent className="bg-[#0A0A0A] border-[#27272A]">
                    <DialogHeader><DialogTitle>Nova Conta</DialogTitle></DialogHeader>
                    <div className="space-y-3 py-2">
                      <div><Label className="text-sm">Descrição</Label><Input value={newBill.description} onChange={e => setNewBill({...newBill, description: e.target.value})} className="bg-[#121212] border-[#27272A]" /></div>
                      <div><Label className="text-sm">Valor (R$)</Label><Input type="number" step="0.01" value={newBill.amount} onChange={e => setNewBill({...newBill, amount: e.target.value})} className="bg-[#121212] border-[#27272A]" /></div>
                      <Button onClick={handleAddBill} className="w-full bg-[#007AFF]">Adicionar</Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              {monthlyBills && (
                <>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <p className="text-xs text-[#A1A1AA]">Total</p>
                      <p className="text-lg font-bold text-white">R$ {monthlyBills.total?.toFixed(2)}</p>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <p className="text-xs text-[#A1A1AA]">Pago</p>
                      <p className="text-lg font-bold text-green-400">R$ {monthlyBills.total_paid?.toFixed(2)}</p>
                    </Card>
                    <Card className="bg-[#0A0A0A] border-[#27272A] p-4 text-center">
                      <p className="text-xs text-[#A1A1AA]">Pendente</p>
                      <p className="text-lg font-bold text-red-400">R$ {monthlyBills.total_pending?.toFixed(2)}</p>
                    </Card>
                  </div>

                  <div className="space-y-2">
                    {(monthlyBills.bills || []).length === 0 ? (
                      <Card className="bg-[#0A0A0A] border-[#27272A] p-8 text-center">
                        <Calendar className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                        <p className="text-[#A1A1AA]">Nenhuma conta para este mês</p>
                        <p className="text-xs text-[#52525B]">Adicione manualmente ou as projeções serão importadas automaticamente</p>
                      </Card>
                    ) : (
                      (monthlyBills.bills || []).map(bill => (
                        <Card key={bill.bill_id} className={`bg-[#0A0A0A] border-[#27272A] p-3 flex items-center gap-3 ${bill.paid ? 'opacity-60' : ''}`}>
                          <button onClick={() => handleToggleBill(bill.bill_id)} className="flex-shrink-0">
                            {bill.paid ? <CheckSquare className="w-5 h-5 text-green-400" /> : <Square className="w-5 h-5 text-[#52525B]" />}
                          </button>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm font-medium truncate ${bill.paid ? 'line-through text-[#52525B]' : ''}`}>{bill.description}</p>
                            <div className="flex items-center gap-2">
                              {bill.installment_info && <span className="text-[10px] text-purple-400">Parcela {bill.installment_info}</span>}
                              {bill.source === 'projection' && <span className="text-[10px] text-blue-400">Via projeção</span>}
                            </div>
                          </div>
                          <span className={`text-sm font-bold ${bill.paid ? 'text-green-400' : 'text-red-400'}`}>R$ {bill.amount?.toFixed(2)}</span>
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-[#52525B] hover:text-red-400" onClick={() => handleDeleteBill(bill.bill_id)}><Trash2 className="w-3 h-3" /></Button>
                        </Card>
                      ))
                    )}
                  </div>
                </>
              )}
            </TabsContent>

            {/* ===== CHAT FINANCEIRO TAB ===== */}
            <TabsContent value="finance_chat" className="mt-6">
              <Card className="bg-[#0A0A0A] border-[#27272A] h-[500px] flex flex-col">
                <div className="p-4 border-b border-[#27272A]">
                  <h3 className="text-sm font-medium flex items-center gap-2"><MessageSquare className="w-4 h-4 text-[#007AFF]" />Assistente Financeiro</h3>
                  <p className="text-xs text-[#52525B]">Pergunte sobre finanças, investimentos, economia...</p>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {chatMessages.length === 0 && (
                    <div className="text-center py-10">
                      <DollarSign className="w-10 h-10 text-[#52525B] mx-auto mb-2" />
                      <p className="text-sm text-[#A1A1AA]">Pergunte qualquer coisa sobre finanças!</p>
                      <p className="text-xs text-[#52525B]">Ex: "Como economizar mais?" ou "Devo investir em renda fixa?"</p>
                    </div>
                  )}
                  {chatMessages.map(msg => (
                    <div key={msg.message_id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] p-3 rounded-lg text-sm whitespace-pre-wrap ${msg.role === 'user' ? 'bg-[#007AFF] text-white' : 'bg-[#121212] text-[#E4E4E7]'}`}>{msg.content}</div>
                    </div>
                  ))}
                  {chatLoading && <div className="flex justify-start"><div className="bg-[#121212] p-3 rounded-lg"><Loader2 className="w-4 h-4 animate-spin text-[#007AFF]" /></div></div>}
                </div>
                <form onSubmit={handleSendFinanceChat} className="p-3 border-t border-[#27272A] flex gap-2">
                  <Input value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Pergunte sobre finanças..." className="bg-[#121212] border-[#27272A] text-sm" disabled={chatLoading} />
                  <Button type="submit" disabled={chatLoading || !chatInput.trim()} size="icon" className="bg-[#007AFF] shrink-0"><Send className="w-4 h-4" /></Button>
                </form>
              </Card>
            </TabsContent>

            {/* CATEGORIES TAB */}
            <TabsContent value="categories" className="mt-6">
              <div className="space-y-6">
                {/* Add new category */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <h3 className="font-heading text-lg mb-4">ADICIONAR CATEGORIA</h3>
                  <div className="flex gap-2">
                    <Input
                      value={newCategoryName}
                      onChange={(e) => setNewCategoryName(e.target.value)}
                      placeholder="Nome da nova categoria..."
                      className="bg-[#121212] border-[#27272A] text-white flex-1"
                      onKeyDown={(e) => e.key === 'Enter' && handleCreateCategory()}
                      maxLength={30}
                    />
                    <Button 
                      onClick={handleCreateCategory} 
                      disabled={categoryLoading || !newCategoryName.trim()}
                      className="bg-[#007AFF] hover:bg-[#0062CC]"
                    >
                      <Plus className="w-4 h-4 mr-2" /> Adicionar
                    </Button>
                  </div>
                  <p className="text-xs text-[#52525B] mt-2">Máximo 30 caracteres. A categoria será convertida para minúsculas.</p>
                </Card>

                {/* Category List */}
                <Card className="bg-[#0A0A0A] border-[#27272A] p-6">
                  <h3 className="font-heading text-lg mb-4">SUAS CATEGORIAS ({categories.length})</h3>
                  <div className="space-y-2">
                    {allCategoriesData.length > 0 ? allCategoriesData.map((cat, idx) => (
                      <div 
                        key={cat.name} 
                        className="flex items-center justify-between p-3 rounded bg-[#121212] border border-[#27272A] hover:border-[#3f3f46] transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-[#52525B] text-sm font-mono w-6">{idx + 1}.</span>
                          <span className="text-white capitalize">{cat.name}</span>
                          {cat.is_default && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#007AFF]/20 text-[#007AFF] border border-[#007AFF]/30">
                              padrão
                            </span>
                          )}
                        </div>
                        {!cat.is_default && (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleDeleteCategory(cat.name)}
                            className="text-red-500 hover:text-red-400 h-8 w-8 p-0"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    )) : categories.map((cat, idx) => (
                      <div 
                        key={cat} 
                        className="flex items-center justify-between p-3 rounded bg-[#121212] border border-[#27272A]"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-[#52525B] text-sm font-mono w-6">{idx + 1}.</span>
                          <span className="text-white capitalize">{cat}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </TabsContent>

          </Tabs>
        </div>
      </div>
      <MobileNav user={user} />
    </div>
  );
}
