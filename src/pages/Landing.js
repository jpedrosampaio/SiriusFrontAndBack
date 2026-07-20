import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useRef } from "react";
import { 
  Shield, Target, TrendingUp, Award, Brain, BarChart3, 
  Dumbbell, Apple, BookOpen, MessageSquare, Bell, Zap,
  CheckCircle2, ChevronRight, ArrowRight, DollarSign, 
  Calendar, Trophy, Flame, Sparkles
} from "lucide-react";
import { SiriusLogo } from "@/components/Sidebar";

function FadeIn({ children, className, delay }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { threshold: 0.1 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={[
        "transition-all duration-700",
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8",
        className || ""
      ].join(" ")}
      style={{ transitionDelay: (delay || 0) + "ms" }}
    >
      {children}
    </div>
  );
}

function AnimatedNumber({ end, label }) {
  const [count, setCount] = useState(0);
  const [started, setStarted] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setStarted(true); },
      { threshold: 0.3 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    let start;
    const dur = 1800;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / dur, 1);
      setCount(Math.floor(p * end));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [started, end]);

  return (
    <div ref={ref} className="text-center">
      <p className="font-heading text-3xl sm:text-4xl text-[#007AFF]">{count}+</p>
      <p className="text-xs text-[#52525B] uppercase tracking-wider mt-1">{label}</p>
    </div>
  );
}

function ModuleCard({ icon, name, desc, color }) {
  const Icon = icon;
  return (
    <div className="group bg-[#0A0A0A] border border-[#1A1A1A] hover:border-[#333] p-5 sm:p-6 rounded-lg transition-all duration-300 hover:-translate-y-0.5 cursor-default">
      <Icon className="w-8 h-8 mb-3" style={{ color }} />
      <h3 className="font-heading text-lg mb-1">{name}</h3>
      <p className="text-[#52525B] text-xs leading-relaxed">{desc}</p>
    </div>
  );
}

function FeatureSpotlight({ badge, title, desc, items, icon, accentColor, image, reversed }) {
  const Icon = icon;
  return (
    <div className={"flex flex-col gap-10 lg:gap-16 items-center " + (reversed ? "lg:flex-row-reverse" : "lg:flex-row")}>
      <div className="flex-1 space-y-5">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#27272A] bg-[#0A0A0A]">
          <Icon className="w-4 h-4" style={{ color: accentColor }} />
          <span className="text-xs uppercase tracking-wider" style={{ color: accentColor }}>{badge}</span>
        </div>
        <h3 className="font-heading text-3xl sm:text-4xl">{title}</h3>
        <p className="text-[#A1A1AA] leading-relaxed">{desc}</p>
        <ul className="space-y-2.5">
          {items.map((item, j) => (
            <li key={j} className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" style={{ color: accentColor }} />
              <span className="text-sm text-[#D4D4D8]">{item}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="flex-1 w-full">
        <div className="relative rounded-xl overflow-hidden border border-[#1A1A1A]">
          <img 
            src={image} 
            alt={title}
            className="w-full h-[280px] sm:h-[340px] object-cover opacity-70 hover:opacity-90 transition-opacity duration-500"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-transparent to-transparent opacity-60" />
        </div>
      </div>
    </div>
  );
}

const MODULES = [
  { icon: CheckCircle2, name: "Tarefas", desc: "Organize e execute com precisão", color: "#007AFF" },
  { icon: TrendingUp, name: "Hábitos", desc: "Construa streaks inquebráveis", color: "#39FF14" },
  { icon: DollarSign, name: "Finanças", desc: "Controle total do seu dinheiro", color: "#FF9500" },
  { icon: BookOpen, name: "Estudos", desc: "IA, flashcards, simulados e mais", color: "#A855F7" },
  { icon: Dumbbell, name: "Treinos", desc: "Planos gerados por IA com tutoriais", color: "#EF4444" },
  { icon: Apple, name: "Nutrição", desc: "Calorias, receitas e dietas", color: "#22C55E" },
  { icon: Target, name: "Metas", desc: "Defina, rastreie, conquiste", color: "#F59E0B" },
  { icon: MessageSquare, name: "Assistente IA", desc: "Chat inteligente com Gemini", color: "#00F0FF" },
  { icon: BarChart3, name: "Relatórios", desc: "Insights com inteligência artificial", color: "#8B5CF6" },
  { icon: Bell, name: "Notificações", desc: "Lembretes inteligentes", color: "#EC4899" },
  { icon: Calendar, name: "Projeções", desc: "Visualize o futuro financeiro", color: "#14B8A6" },
  { icon: Trophy, name: "Gamificação", desc: "XP, ranks e conquistas", color: "#FFD700" },
];

const FEATURES = [
  {
    badge: "ESTUDOS COM IA",
    title: "Sua Central de Estudos Completa",
    desc: "Importe editais de concursos em PDF e a IA gera automaticamente um programa de estudos personalizado com cronograma semanal, flashcards com repetição espaçada, simulados por banca, mapas mentais e timer Pomodoro integrado.",
    items: ["Importar edital → Programa automático", "Flashcards com algoritmo SM-2", "Simulados por banca (CESPE, FGV, FCC)", "Mapas mentais gerados por IA", "Timer Pomodoro com estatísticas"],
    icon: BookOpen,
    accentColor: "#A855F7",
    image: "https://images.unsplash.com/photo-1576272531110-2a342fe22342?w=600&h=400&fit=crop"
  },
  {
    badge: "FINANÇAS INTELIGENTES",
    title: "Controle Financeiro Total",
    desc: "Registre gastos por texto ou foto de recibos. A IA analisa suas finanças, projeta gastos futuros, gerencia cartões de crédito com parcelamento e oferece insights personalizados para otimizar seu orçamento.",
    items: ["Chat: 'Gastei 50 no mercado' → registrado", "Foto de nota fiscal → gastos extraídos", "Cartões com parcelamento e fatura", "Projeção de gastos futuros", "Relatórios e insights com IA"],
    icon: DollarSign,
    accentColor: "#FF9500",
    image: "https://images.unsplash.com/photo-1659079631735-2228a7ce943e?w=600&h=400&fit=crop"
  },
  {
    badge: "TREINOS & NUTRIÇÃO",
    title: "Corpo e Mente em Sincronia",
    desc: "Gere planos de treino com IA incluindo tutoriais e vídeos do YouTube. Acompanhe sessões em tempo real, registre medidas corporais, controle calorias, macros e hidratação. Receba receitas personalizadas da IA.",
    items: ["Planos de treino gerados por IA", "Sessão ativa com timer e séries", "Controle calórico e de macros", "Receitas sugeridas pela IA", "Bioimpedância e evolução corporal"],
    icon: Dumbbell,
    accentColor: "#EF4444",
    image: "https://images.unsplash.com/photo-1586797513138-b7336cd82a7f?w=600&h=400&fit=crop"
  }
];

const RANKS = ["Recruta", "Soldado", "Cabo", "Sargento", "Subtenente", "Tenente", "Capitão", "Major", "Coronel", "General", "Marechal"];

export default function Landing() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const rankColor = (i) => {
    if (i === 0) return "bg-[#52525B] text-white";
    if (i < 4) return "bg-[#007AFF]/20 text-[#007AFF] border border-[#007AFF]/30";
    if (i < 7) return "bg-[#FF9500]/20 text-[#FF9500] border border-[#FF9500]/30";
    if (i < 10) return "bg-[#A855F7]/20 text-[#A855F7] border border-[#A855F7]/30";
    return "bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/30";
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white overflow-x-hidden">
      {/* NAV */}
      <nav className={"fixed w-full top-0 z-50 transition-all duration-300 " + (scrolled ? "bg-[#0A0A0A]/90 backdrop-blur-xl border-b border-[#27272A] shadow-lg shadow-black/20" : "bg-transparent")}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
          <div className="flex items-center space-x-2 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            <SiriusLogo size="w-8 h-8" />
            <span className="font-heading text-2xl bg-gradient-to-r from-[#00F0FF] to-[#007AFF] bg-clip-text text-transparent">SIRIUS</span>
          </div>
          <div className="hidden md:flex items-center space-x-6">
            <a href="#modules" className="text-sm text-[#A1A1AA] hover:text-white transition-colors">Módulos</a>
            <a href="#details" className="text-sm text-[#A1A1AA] hover:text-white transition-colors">Destaques</a>
            <a href="#gamification" className="text-sm text-[#A1A1AA] hover:text-white transition-colors">Gamificação</a>
          </div>
          <div className="flex items-center space-x-3">
            <Button data-testid="landing-login-btn" variant="ghost" onClick={() => navigate("/login")} className="text-sm text-[#A1A1AA] hover:text-white">
              Login
            </Button>
            <Button data-testid="landing-register-btn" onClick={() => navigate("/register")} className="bg-[#007AFF] hover:bg-[#0062CC] text-sm shadow-[0_0_20px_rgba(0,122,255,0.3)]">
              Começar Grátis
            </Button>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="relative pt-28 pb-20 sm:pt-36 sm:pb-28 px-4 overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-[#007AFF]/5 blur-[120px]" />
          <div className="absolute bottom-0 left-1/4 w-[400px] h-[400px] rounded-full bg-[#00F0FF]/5 blur-[100px]" />
          <div className="absolute top-0 right-0 w-[300px] h-[300px] rounded-full bg-[#A855F7]/5 blur-[80px]" />
        </div>
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <FadeIn>
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#27272A] bg-[#0A0A0A]/80 backdrop-blur-sm mb-8">
              <Sparkles className="w-4 h-4 text-[#00F0FF]" />
              <span className="text-xs text-[#A1A1AA] uppercase tracking-wider">Powered by Google Gemini AI</span>
            </div>
          </FadeIn>
          <FadeIn delay={100}>
            <h1 className="font-heading text-5xl sm:text-6xl lg:text-8xl mb-6 tracking-tight leading-[0.9]">
              <span className="block">DISCIPLINA</span>
              <span className="block bg-gradient-to-r from-[#00F0FF] via-[#007AFF] to-[#A855F7] bg-clip-text text-transparent">É DESTINO</span>
            </h1>
          </FadeIn>
          <FadeIn delay={200}>
            <p className="text-lg sm:text-xl text-[#A1A1AA] max-w-2xl mx-auto mb-10 leading-relaxed">
              O sistema completo que une <strong className="text-white">produtividade</strong>, <strong className="text-white">finanças</strong>, <strong className="text-white">estudos</strong>, <strong className="text-white">treinos</strong> e <strong className="text-white">nutrição</strong> em uma única plataforma gamificada com inteligência artificial.
            </p>
          </FadeIn>
          <FadeIn delay={300}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button data-testid="landing-start-btn" size="lg" onClick={() => navigate("/register")} className="bg-[#007AFF] hover:bg-[#0062CC] h-14 px-10 text-base font-medium shadow-[0_0_30px_rgba(0,122,255,0.4)] transition-all group">
                Iniciar Missão
                <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
              <Button variant="outline" size="lg" onClick={() => document.getElementById("modules")?.scrollIntoView({ behavior: "smooth" })} className="h-14 px-10 text-base border-[#27272A] hover:bg-[#121212] text-[#A1A1AA] hover:text-white">
                Ver Funcionalidades
              </Button>
            </div>
          </FadeIn>
          <FadeIn delay={400}>
            <div className="mt-16 grid grid-cols-3 gap-8 max-w-lg mx-auto">
              <AnimatedNumber end={12} label="Módulos" />
              <AnimatedNumber end={50} label="Endpoints IA" />
              <AnimatedNumber end={100} label="Grátis" />
            </div>
          </FadeIn>
        </div>
      </section>

      {/* MODULES */}
      <section id="modules" className="py-20 px-4 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0A0A0A]/50 to-transparent pointer-events-none" />
        <div className="max-w-7xl mx-auto relative z-10">
          <FadeIn>
            <div className="text-center mb-14">
              <p className="text-xs text-[#007AFF] uppercase tracking-[0.3em] mb-3 font-medium">Ecossistema Completo</p>
              <h2 className="font-heading text-4xl sm:text-5xl">TUDO EM UM SÓ LUGAR</h2>
              <p className="text-[#71717A] mt-4 max-w-xl mx-auto">12 módulos integrados que conversam entre si. Seus dados de treino influenciam suas metas de nutrição. Seus estudos geram XP. Tudo conectado.</p>
            </div>
          </FadeIn>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
            {MODULES.map((mod, i) => (
              <FadeIn key={mod.name} delay={i * 60}>
                <ModuleCard icon={mod.icon} name={mod.name} desc={mod.desc} color={mod.color} />
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURE SPOTLIGHTS */}
      <section id="details" className="py-20 px-4">
        <div className="max-w-7xl mx-auto space-y-28">
          {FEATURES.map((feat, idx) => (
            <FadeIn key={feat.title}>
              <FeatureSpotlight
                badge={feat.badge}
                title={feat.title}
                desc={feat.desc}
                items={feat.items}
                icon={feat.icon}
                accentColor={feat.accentColor}
                image={feat.image}
                reversed={idx % 2 === 1}
              />
            </FadeIn>
          ))}
        </div>
      </section>

      {/* GAMIFICATION */}
      <section id="gamification" className="py-20 px-4 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#007AFF]/[0.03] to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto relative z-10">
          <FadeIn>
            <div className="text-center mb-14">
              <p className="text-xs text-[#FFD700] uppercase tracking-[0.3em] mb-3 font-medium">Sistema de Ranking</p>
              <h2 className="font-heading text-4xl sm:text-5xl">GAMIFICAÇÃO MILITAR</h2>
              <p className="text-[#71717A] mt-4 max-w-xl mx-auto">Cada ação gera XP. Suba de rank, de Recruta a Marechal. 14 níveis para conquistar.</p>
            </div>
          </FadeIn>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <FadeIn delay={0}>
              <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-7 text-center hover:border-[#FFD700]/30 transition-colors">
                <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-[#FFD700]/10 flex items-center justify-center">
                  <Zap className="w-7 h-7 text-[#FFD700]" />
                </div>
                <h4 className="font-heading text-xl mb-2">GANHE XP</h4>
                <p className="text-sm text-[#52525B]">Tarefas, hábitos, treinos, estudos — tudo gera pontos de experiência</p>
              </div>
            </FadeIn>
            <FadeIn delay={100}>
              <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-7 text-center hover:border-[#007AFF]/30 transition-colors">
                <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-[#007AFF]/10 flex items-center justify-center">
                  <Award className="w-7 h-7 text-[#007AFF]" />
                </div>
                <h4 className="font-heading text-xl mb-2">SUBA DE RANK</h4>
                <p className="text-sm text-[#52525B]">De Recruta a Marechal — 14 patentes inspiradas na hierarquia militar</p>
              </div>
            </FadeIn>
            <FadeIn delay={200}>
              <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-7 text-center hover:border-[#39FF14]/30 transition-colors">
                <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-[#39FF14]/10 flex items-center justify-center">
                  <Flame className="w-7 h-7 text-[#39FF14]" />
                </div>
                <h4 className="font-heading text-xl mb-2">MANTENHA STREAKS</h4>
                <p className="text-sm text-[#52525B]">Sequências de dias produtivos que multiplicam seus ganhos de XP</p>
              </div>
            </FadeIn>
          </div>
          <FadeIn delay={300}>
            <div className="mt-10 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-6 sm:p-8">
              <p className="text-xs text-[#52525B] uppercase tracking-wider mb-4 text-center">Progressão de Ranks</p>
              <div className="flex items-center justify-between overflow-x-auto gap-1 pb-2">
                {RANKS.map((rank, i) => (
                  <div key={rank} className="flex flex-col items-center min-w-[60px]">
                    <div className={"w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold " + rankColor(i)}>
                      {i + 1}
                    </div>
                    <span className="text-[8px] text-[#52525B] mt-1.5 text-center leading-tight">{rank}</span>
                  </div>
                ))}
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* AI SECTION */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <FadeIn>
            <div className="relative bg-gradient-to-br from-[#007AFF]/10 via-[#0A0A0A] to-[#A855F7]/10 border border-[#1A1A1A] rounded-2xl p-8 sm:p-12 overflow-hidden">
              <div className="absolute top-0 right-0 w-[300px] h-[300px] rounded-full bg-[#007AFF]/5 blur-[80px] pointer-events-none" />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#007AFF] to-[#A855F7] flex items-center justify-center">
                    <Brain className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="font-heading text-2xl">ASSISTENTE IA INTEGRADO</h3>
                    <p className="text-xs text-[#52525B]">Powered by Google Gemini 2.5 Flash</p>
                  </div>
                </div>
                <p className="text-[#A1A1AA] mb-8 leading-relaxed max-w-2xl">
                  Converse naturalmente com o Sirius. Registre gastos por texto, peça receitas, gere planos de treino, 
                  importe editais de concurso, analise fotos de recibos — tudo pela conversa.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    '"Gastei 150 no supermercado e 30 de uber"',
                    '"Gere um treino de peito para intermediário"',
                    '"Sugira uma receita com frango e brócolis"',
                    '"Como estão minhas finanças este mês?"',
                  ].map((example, i) => (
                    <div key={i} className="flex items-center gap-3 bg-[#050505]/60 border border-[#27272A] rounded-lg px-4 py-3">
                      <MessageSquare className="w-4 h-4 text-[#007AFF] flex-shrink-0" />
                      <span className="text-sm text-[#D4D4D8] italic">{example}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="py-24 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <FadeIn>
            <h2 className="font-heading text-4xl sm:text-5xl lg:text-6xl mb-6">
              PRONTO PARA A
              <span className="block bg-gradient-to-r from-[#00F0FF] to-[#007AFF] bg-clip-text text-transparent">MISSÃO?</span>
            </h2>
            <p className="text-[#71717A] text-lg mb-10 max-w-xl mx-auto">
              Junte-se ao Sirius e transforme disciplina em resultados. Sem cartão de crédito. Sem pegadinhas.
            </p>
            <Button size="lg" onClick={() => navigate("/register")} className="bg-[#007AFF] hover:bg-[#0062CC] h-14 px-12 text-base font-medium shadow-[0_0_40px_rgba(0,122,255,0.4)] transition-all group">
              Criar Conta Gratuita
              <ChevronRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Button>
          </FadeIn>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-[#1A1A1A] py-10 px-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <SiriusLogo size="w-6 h-6" />
            <span className="font-heading text-lg bg-gradient-to-r from-[#00F0FF] to-[#007AFF] bg-clip-text text-transparent">SIRIUS</span>
          </div>
          <p className="text-xs text-[#3F3F46]">© 2025 Sirius — Discipline is Destiny. Todos os direitos reservados.</p>
          <div className="flex items-center gap-1 text-xs text-[#3F3F46]">
            <Sparkles className="w-3 h-3" />
            <span>Powered by AI</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
