import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { 
  Dumbbell, DollarSign, BookOpen, Target, 
  Utensils, CheckSquare, TrendingUp, Sparkles,
  ChevronRight, X, Zap
} from "lucide-react";

const ONBOARDING_KEY = "sirius_onboarding_complete";

const steps = [
  {
    icon: Zap,
    color: "#FFD700",
    title: "Bem-vindo ao Sirius!",
    description: "Sua plataforma completa de produtividade, finanças, treinos, nutrição e estudos. Tudo em um só lugar.",
    tip: "Ganhe XP completando atividades e suba de rank!"
  },
  {
    icon: DollarSign,
    color: "#39FF14",
    title: "Finanças Inteligentes",
    description: "Controle transações, orçamentos, cartões de crédito e projeções. Use o Chat Financeiro com IA para insights.",
    tip: "Crie categorias personalizadas na aba 'Categorias'"
  },
  {
    icon: Dumbbell,
    color: "#FF6B6B",
    title: "Treinos com IA",
    description: "Gere treinos personalizados com tutoriais e vídeos do YouTube. Inicie sessões com timer e acompanhe seu progresso.",
    tip: "Use 'Gerar com IA' para treinos com tutorial de cada exercício"
  },
  {
    icon: Utensils,
    color: "#4ECDC4",
    title: "Nutrição & Calculadora",
    description: "Registre refeições, gere planos alimentares com IA, calcule IMC/TMB e crie listas de compras automáticas.",
    tip: "A Calculadora de Saúde ajuda a definir suas metas de macros"
  },
  {
    icon: BookOpen,
    color: "#A78BFA",
    title: "Estudos Avançados",
    description: "Cadernos, flashcards com repetição espaçada, simulados, mapas mentais, cronograma e correção de redação com IA.",
    tip: "Importe editais de concursos para criar cronogramas automáticos"
  },
  {
    icon: Target,
    color: "#00F0FF",
    title: "Tudo Conectado",
    description: "Dashboard com resumo semanal, busca global, lembretes inteligentes e sugestões entre módulos. Vamos começar!",
    tip: "Use a barra de busca no Dashboard para encontrar qualquer coisa"
  }
];

export default function Onboarding({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const completed = localStorage.getItem(ONBOARDING_KEY);
    if (!completed) {
      setVisible(true);
    }
  }, []);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setVisible(false);
    onComplete && onComplete();
  };

  if (!visible) return null;

  const step = steps[currentStep];
  const Icon = step.icon;

  return (
    <div className="fixed inset-0 z-[200] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0A0A0A] border border-[#27272A] rounded-2xl max-w-md w-full overflow-hidden">
        {/* Header with close */}
        <div className="flex justify-between items-center p-4 border-b border-[#27272A]">
          <div className="flex gap-1">
            {steps.map((_, i) => (
              <div 
                key={i} 
                className={`h-1.5 rounded-full transition-all ${
                  i === currentStep ? 'w-8 bg-[#007AFF]' : i < currentStep ? 'w-4 bg-[#007AFF]/50' : 'w-4 bg-[#27272A]'
                }`} 
              />
            ))}
          </div>
          <button onClick={handleComplete} className="text-[#52525B] hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-8 text-center">
          <div 
            className="w-20 h-20 rounded-2xl mx-auto mb-6 flex items-center justify-center"
            style={{ backgroundColor: `${step.color}15`, border: `2px solid ${step.color}30` }}
          >
            <Icon className="w-10 h-10" style={{ color: step.color }} />
          </div>

          <h2 className="font-heading text-2xl mb-3">{step.title}</h2>
          <p className="text-[#A1A1AA] text-sm leading-relaxed mb-4">{step.description}</p>

          {step.tip && (
            <div className="bg-[#121212] border border-[#27272A] rounded-lg p-3 mb-6">
              <p className="text-xs text-[#FFD700] flex items-center gap-2 justify-center">
                <Sparkles className="w-3 h-3" /> {step.tip}
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-[#27272A] flex justify-between items-center">
          <button onClick={handleComplete} className="text-sm text-[#52525B] hover:text-white">
            Pular tour
          </button>
          <Button onClick={handleNext} className="bg-[#007AFF] hover:bg-[#0062CC]">
            {currentStep < steps.length - 1 ? (
              <>Próximo <ChevronRight className="w-4 h-4 ml-1" /></>
            ) : (
              <>Começar! <Sparkles className="w-4 h-4 ml-1" /></>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
