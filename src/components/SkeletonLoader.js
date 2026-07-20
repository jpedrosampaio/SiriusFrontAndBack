import React from 'react';

function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse bg-[#27272A]/50 rounded-sm ${className}`} />
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-[#0A0A0A] border border-[#27272A] rounded-sm p-4 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

export function ListSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bg-[#0A0A0A] border border-[#27272A] rounded-sm p-3 flex items-center space-x-3">
          <Skeleton className="w-10 h-10 rounded-sm flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="w-16 h-6 rounded-sm" />
        </div>
      ))}
    </div>
  );
}

export function GridSkeleton({ cols = 3, rows = 2 }) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-${cols} gap-4`}>
      {Array.from({ length: cols * rows }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
          <div className={`flex items-start space-x-2 max-w-[70%] ${i % 2 === 0 ? 'flex-row-reverse space-x-reverse' : ''}`}>
            <Skeleton className="w-8 h-8 rounded-sm flex-shrink-0" />
            <div className="space-y-2">
              <Skeleton className="h-12 w-48 rounded-sm" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-[#0A0A0A] border border-[#27272A] rounded-sm p-4">
            <Skeleton className="h-3 w-20 mb-2" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
      {/* Content */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#0A0A0A] border border-[#27272A] rounded-sm p-4 space-y-3">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-24 w-full" />
        </div>
        <div className="bg-[#0A0A0A] border border-[#27272A] rounded-sm p-4 space-y-3">
          <Skeleton className="h-5 w-32" />
          <ListSkeleton rows={3} />
        </div>
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4">
        <Skeleton className="w-20 h-20 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <GridSkeleton cols={3} rows={1} />
    </div>
  );
}

export default Skeleton;
