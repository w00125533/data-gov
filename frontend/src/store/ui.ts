import { create } from 'zustand'

type UiState = {
  selectedTable?: string
  setSelectedTable: (table?: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  selectedTable: undefined,
  setSelectedTable: (selectedTable) => set({ selectedTable }),
}))
