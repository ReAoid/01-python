# 前端项目说明

## 依赖说明

### PixiJS 依赖配置
本项目使用 `pixi-live2d-display@0.5.0-beta` 来渲染 Live2D 模型，该库需要以下依赖：

```json
{
  "dependencies": {
    "pixi.js": "^7.4.2",
    "@pixi/core": "^7.4.3",
    "@pixi/display": "^7.4.3",
    "@pixi/math": "^7.4.3",
    "@pixi/sprite": "^7.4.3",
    "@pixi/ticker": "^7.4.3",
    "pixi-live2d-display": "0.5.0-beta"
  }
}
```

#### 为什么需要同时安装 `pixi.js` 和 `@pixi/*` 包？

- **`pixi.js`**: PixiJS 的完整打包版本，包含所有功能
- **`@pixi/*`**: PixiJS 的模块化包，允许按需导入特定模块

`pixi-live2d-display@0.5.0-beta` 内部使用模块化导入方式（如 `import { Container } from "@pixi/display"`），因此必须安装对应的 `@pixi/*` 包才能正常工作。

#### 常见错误

如果遇到以下构建错误：
```
ERROR: Could not resolve "@pixi/core"
ERROR: Could not resolve "@pixi/display"
```

说明缺少 PixiJS 模块化依赖包，请执行：
```bash
npm install @pixi/core @pixi/display @pixi/math @pixi/sprite @pixi/ticker
```

## 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## Live2D 测试

启动开发服务器后，访问以下页面测试 Live2D 功能：
- http://localhost:5173/test-live2d.html

## 技术栈

- **Vue 3** - 前端框架
- **Vite** - 构建工具
- **TailwindCSS** - CSS 框架
- **PixiJS 7** - 2D 渲染引擎
- **pixi-live2d-display** - Live2D 模型渲染库
