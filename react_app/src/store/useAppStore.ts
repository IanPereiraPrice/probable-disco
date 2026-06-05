import { create } from 'zustand'
import type { UserData } from '@/api/types'

interface AppStore {
  userData: UserData | null
  isLoading: boolean
  username: string

  // Actions
  setUserData: (data: UserData) => void
  setLoading: (loading: boolean) => void
  updateCharacterField: <K extends keyof UserData>(field: K, value: UserData[K]) => void
  updateEquipmentItem: (slot: string, itemData: Record<string, unknown>) => void
  updateEquipmentPotential: (slot: string, potData: Record<string, unknown>) => void
  updateEquipmentScroll: (slot: string, scrollData: Record<string, unknown>) => void
}

export const useAppStore = create<AppStore>((set) => ({
  userData: null,
  isLoading: false,
  username: 'default',

  setUserData: (data) => set({ userData: data }),
  setLoading: (loading) => set({ isLoading: loading }),

  updateCharacterField: (field, value) =>
    set((state) => ({
      userData: state.userData ? { ...state.userData, [field]: value } : null,
    })),

  updateEquipmentItem: (slot, itemData) =>
    set((state) => ({
      userData: state.userData
        ? {
            ...state.userData,
            equipment_items: { ...state.userData.equipment_items, [slot]: itemData },
          }
        : null,
    })),

  updateEquipmentPotential: (slot, potData) =>
    set((state) => ({
      userData: state.userData
        ? {
            ...state.userData,
            equipment_potentials: { ...state.userData.equipment_potentials, [slot]: potData },
          }
        : null,
    })),

  updateEquipmentScroll: (slot, scrollData) =>
    set((state) => ({
      userData: state.userData
        ? {
            ...state.userData,
            equipment_scrolls: { ...state.userData.equipment_scrolls, [slot]: scrollData },
          }
        : null,
    })),
}))
