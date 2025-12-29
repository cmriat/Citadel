import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  // 从 localStorage 读取主题，默认为 dark
  const savedTheme = localStorage.getItem('theme') as ThemeMode | null
  const theme = ref<ThemeMode>(savedTheme || 'dark')

  const isDark = () => theme.value === 'dark'

  const setTheme = (newTheme: ThemeMode) => {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
    applyTheme(newTheme)
  }

  const toggleTheme = () => {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  const applyTheme = (themeMode: ThemeMode) => {
    const html = document.documentElement
    if (themeMode === 'dark') {
      html.classList.add('dark')
      html.classList.remove('light')
    } else {
      html.classList.add('light')
      html.classList.remove('dark')
    }
  }

  // 初始化时应用主题
  applyTheme(theme.value)

  // 监听主题变化
  watch(theme, (newTheme) => {
    applyTheme(newTheme)
  })

  return {
    theme,
    isDark,
    setTheme,
    toggleTheme
  }
})
