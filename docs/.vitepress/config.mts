import { defineConfig } from 'vitepress'

const repository = process.env.GITHUB_REPOSITORY

export default defineConfig({
  title: 'HIWM Interaction Demo',
  description: '人际互动世界模型的交互决策演示平台',
  base: (process.env.VITEPRESS_BASE as '/' | `/${string}/`) || '/',
  srcExclude: ['upstream/**'],
  ignoreDeadLinks: [/^https?:\/\/localhost/],
  lang: 'zh-CN',

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '快速开始', link: '/guides/macos-setup' },
      { text: '运行架构', link: '/guides/hiwm-runtime' },
      { text: '研究定义', link: '/research/hiwm-definition.zh-CN' },
      { text: '验收记录', link: '/reports/acceptance-2026-07-18.zh-CN' },
    ],
    sidebar: {
      '/guides/': [
        {
          text: '开发指南',
          items: [
            { text: 'macOS 安装与启动', link: '/guides/macos-setup' },
            { text: 'HIWM 运行架构', link: '/guides/hiwm-runtime' },
          ],
        },
      ],
      '/research/': [
        {
          text: '研究与产品定义',
          items: [
            { text: '正式定义与研究依据', link: '/research/hiwm-definition.zh-CN' },
            { text: '正式 Demo 设计方案', link: '/research/hiwm-demo-design.zh-CN' },
          ],
        },
      ],
      '/reports/': [
        {
          text: '验证记录',
          items: [
            { text: '2026-07-18 软件验收', link: '/reports/acceptance-2026-07-18.zh-CN' },
          ],
        },
      ],
    },
    socialLinks: repository
      ? [{ icon: 'github', link: `https://github.com/${repository}` }]
      : [],
    footer: {
      message: 'Apache-2.0 · 基于 OpenAvatarChat 与 OpenAvatarChat-WebUI 的实质修改版本',
      copyright: '上游归属与第三方许可证见仓库 UPSTREAM.md 和 THIRD_PARTY_NOTICES.md',
    },
  },
})
