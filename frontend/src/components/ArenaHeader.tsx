import React from 'react';
import {ReadingSettings} from '../workbench/ReadingSettings';
import { Play, Sliders, Trophy, BookOpen, Clock, HelpCircle, Sun, Moon, Database } from 'lucide-react';

export type ArenaTab = 'workbench' | 'history' | 'tasks' | 'configs' | 'leaderboard' | 'spec';

interface ArenaHeaderProps {
  activeTab: ArenaTab;
  onTabChange: (tab: ArenaTab) => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const ArenaHeader: React.FC<ArenaHeaderProps> = ({
  activeTab,
  onTabChange,
  theme,
  onToggleTheme,
}) => {
  const tabs = [
    { id: 'workbench' as ArenaTab, label: '评测工作台', icon: Play },
    { id: 'history' as ArenaTab, label: '评测历史', icon: Clock },
    { id: 'tasks' as ArenaTab, label: '题库中心', icon: Database },
    { id: 'configs' as ArenaTab, label: '配置管理', icon: Sliders },
    { id: 'leaderboard' as ArenaTab, label: '同条件结果', icon: Trophy },
    { id: 'spec' as ArenaTab, label: '原理与规范', icon: HelpCircle },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-[#09090b]/95 backdrop-blur-md border-b border-slate-200/90 dark:border-zinc-800 px-3 sm:px-6 py-2.5 select-none transition-colors duration-200">
      <div className="max-w-7xl mx-auto flex flex-wrap xl:flex-nowrap items-center justify-between gap-3 min-w-0">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 font-bold text-xs flex items-center justify-center tracking-tight shadow-sm transition-transform duration-200 hover:scale-105 shrink-0">
            CHB
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-slate-900 dark:text-white">
                Codex Harness Benchmark
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-slate-100 dark:bg-zinc-800 border border-slate-200/80 dark:border-zinc-700 text-slate-600 dark:text-zinc-300 hidden sm:inline">
                本地工作台
              </span>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-zinc-400 hidden md:block">
              保存配置，执行需求，检查实际交付
            </p>
          </div>
        </div>

        {/* Center Tabs */}
        <nav className="order-3 xl:order-none w-full xl:w-auto min-w-0 flex items-center gap-0.5 sm:gap-1 bg-slate-100/90 dark:bg-zinc-900/90 p-1 rounded-xl border border-slate-200/80 dark:border-zinc-800 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-150 ${
                  isActive
                    ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm font-semibold'
                    : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-zinc-800/60'
                }`}
              >
                <Icon
                  className={`w-3.5 h-3.5 ${
                    isActive ? 'text-zinc-900 dark:text-white' : 'text-slate-400 dark:text-zinc-500'
                  }`}
                />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Controls */}
        <div className="flex items-center gap-2 text-xs shrink-0"><ReadingSettings/>
          <button
            onClick={onToggleTheme}
            title={theme === 'light' ? '切换到暗色模式' : '切换到白天模式'}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900 text-slate-700 dark:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-all duration-150 shadow-sm"
          >
            {theme === 'light' ? (
              <>
                <Sun className="w-3.5 h-3.5 text-amber-500" />
                <span className="text-[11px] font-medium hidden lg:inline">白天模式</span>
              </>
            ) : (
              <>
                <Moon className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-[11px] font-medium hidden lg:inline">深色模式</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
