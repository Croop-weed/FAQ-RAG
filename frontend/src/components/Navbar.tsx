import React from 'react';
import { Bot, ShieldCheck, User, Users } from 'lucide-react';

interface NavbarProps {
  activeRole: 'customer' | 'agent';
  onRoleChange: (role: 'customer' | 'agent') => void;
  pendingCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({ activeRole, onRoleChange, pendingCount = 0 }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand logo & tagline */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-600/30">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-100 text-lg tracking-tight">Orbit Desk</span>
              <span className="px-2 py-0.5 text-xs font-medium bg-slate-800 text-slate-300 rounded-full border border-slate-700">
                Support Assistant
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">Human-in-the-Loop RAG Platform</p>
          </div>
        </div>

        {/* Role Switcher Tabs */}
        <div className="flex items-center p-1 bg-slate-950 rounded-xl border border-slate-800">
          <button
            onClick={() => onRoleChange('customer')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeRole === 'customer'
                ? 'bg-slate-800 text-white shadow-sm border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <User className="w-4 h-4 text-emerald-400" />
            Customer Portal
          </button>
          <button
            onClick={() => onRoleChange('agent')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all relative ${
              activeRole === 'agent'
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-4 h-4 text-indigo-200" />
            Agent Workspace
            {pendingCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 text-[10px] font-bold bg-amber-500 text-slate-950 rounded-full">
                {pendingCount}
              </span>
            )}
          </button>
        </div>

        {/* Safety Banner Indicator */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-emerald-950/60 border border-emerald-800/50 rounded-lg text-emerald-300 text-xs font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Human Review Mandatory</span>
        </div>
      </div>
    </header>
  );
};
