/**
 * 应用入口文件 (Entry Point)
 * -------------------------------------------------------------------------
 * 负责初始化 Vue 应用实例，并挂载全局依赖。
 * 
 * 主要职责:
 * 1. 引入 Vue 核心库
 * 2. 引入全局样式 (Tailwind 指令 + 自定义样式)
 * 3. 引入 FontAwesome 图标库
 * 4. 挂载根组件 App.vue 到 DOM
 */

import { createApp } from 'vue'
import './style.css' // 全局样式 (包含 Tailwind @tailwind 指令)
import App from './App.vue'
import '@fortawesome/fontawesome-free/css/all.css' // 引入 FontAwesome 图标库

// 创建并挂载 Vue 应用
createApp(App).mount('#app')
