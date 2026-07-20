import { useState, useEffect } from "react";
import { Zap, Trophy, Star } from "lucide-react";

export function XpAnimation({ amount, show, onComplete }) {
  const [visible, setVisible] = useState(false);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    if (show && amount > 0) {
      setVisible(true);
      setAnimating(true);
      const timer = setTimeout(() => {
        setAnimating(false);
        setTimeout(() => {
          setVisible(false);
          onComplete && onComplete();
        }, 300);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [show, amount, onComplete]);

  if (!visible) return null;

  return (
    <div className={`fixed inset-0 pointer-events-none z-[100] flex items-center justify-center transition-opacity duration-300 ${animating ? 'opacity-100' : 'opacity-0'}`}>
      <div className={`transform transition-all duration-700 ${animating ? 'scale-100 translate-y-0' : 'scale-50 translate-y-20'}`}>
        <div className="bg-[#0A0A0A]/90 backdrop-blur-xl border-2 border-[#FFD700] rounded-2xl p-8 text-center shadow-2xl shadow-[#FFD700]/20">
          <div className="relative">
            {/* Sparkle effects */}
            <div className="absolute -top-4 -left-4 animate-ping">
              <Star className="w-4 h-4 text-[#FFD700]" />
            </div>
            <div className="absolute -top-2 -right-6 animate-ping delay-150">
              <Star className="w-3 h-3 text-[#00F0FF]" />
            </div>
            <div className="absolute -bottom-3 -right-4 animate-ping delay-300">
              <Star className="w-5 h-5 text-[#A855F7]" />
            </div>
            
            <Zap className="w-12 h-12 text-[#FFD700] mx-auto mb-3 animate-bounce" />
            <p className="text-[#FFD700] text-sm uppercase tracking-wider font-bold mb-1">XP Ganho!</p>
            <p className="font-data text-5xl text-white">+{amount}</p>
            <p className="text-[#A1A1AA] text-xs mt-2">Continue assim!</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function RankUpAnimation({ newRank, show, onComplete }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (show && newRank) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
        onComplete && onComplete();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [show, newRank, onComplete]);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 pointer-events-none z-[100] flex items-center justify-center">
      <div className="bg-[#0A0A0A]/95 backdrop-blur-xl border-2 border-[#A855F7] rounded-2xl p-10 text-center shadow-2xl animate-[bounceIn_0.5s_ease-out]">
        <Trophy className="w-16 h-16 text-[#FFD700] mx-auto mb-4 animate-bounce" />
        <p className="text-[#A855F7] text-sm uppercase tracking-wider font-bold mb-2">Rank Up!</p>
        <p className="font-heading text-3xl text-white">{newRank}</p>
        <p className="text-[#A1A1AA] text-sm mt-2">Parabéns pela evolução!</p>
      </div>
    </div>
  );
}

export function LoadingSkeleton({ type = "card", count = 3 }) {
  const skeletons = Array.from({ length: count });

  if (type === "card") {
    return (
      <div className="space-y-4">
        {skeletons.map((_, i) => (
          <div key={i} className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-6 animate-pulse">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#27272A]" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-[#27272A] rounded w-1/3" />
                <div className="h-3 bg-[#1a1a1a] rounded w-2/3" />
              </div>
            </div>
            <div className="space-y-2">
              <div className="h-3 bg-[#1a1a1a] rounded w-full" />
              <div className="h-3 bg-[#1a1a1a] rounded w-4/5" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (type === "stats") {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {skeletons.map((_, i) => (
          <div key={i} className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-6 animate-pulse">
            <div className="flex justify-between mb-4">
              <div className="w-8 h-8 rounded bg-[#27272A]" />
              <div className="w-16 h-6 rounded bg-[#27272A]" />
            </div>
            <div className="h-3 bg-[#1a1a1a] rounded w-2/3" />
          </div>
        ))}
      </div>
    );
  }

  if (type === "list") {
    return (
      <div className="space-y-2">
        {skeletons.map((_, i) => (
          <div key={i} className="bg-[#0A0A0A] border border-[#27272A] rounded-lg p-4 animate-pulse flex items-center gap-3">
            <div className="w-6 h-6 rounded bg-[#27272A]" />
            <div className="flex-1 space-y-1">
              <div className="h-4 bg-[#27272A] rounded w-1/2" />
              <div className="h-3 bg-[#1a1a1a] rounded w-1/3" />
            </div>
            <div className="w-12 h-4 rounded bg-[#1a1a1a]" />
          </div>
        ))}
      </div>
    );
  }

  return null;
}
