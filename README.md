# AwesomeTechBooks 平台

组织里所有书共用的网页底层：阅读器外壳、共享样式和组件、入口页生成器、构建发布流水线。
书的仓库只放内容，怎么构建、怎么发布、页面外壳长什么样，都在这里统一定义。

## 仓库分工

| 仓库 | 放什么 | 网址 |
|---|---|---|
| `platform`（本仓库） | 代码：阅读器、组件的标准版本、构建工具、入口页模板、可复用工作流 | 不单独发布 |
| `AwesomeTechBooks.github.io` | 数据：书目 `catalog.json`；构建出首页 | <https://awesometechbooks.github.io/> |
| `.github` | 组织主页的 `profile/README.md`，由书目生成 | <https://github.com/AwesomeTechBooks> |
| 每本书一个仓库，名字即目录名 | mdBook 源码（`book.toml`、`src/`、`theme/`、`LICENSE*`），或现成的 HTML | `https://awesometechbooks.github.io/<书名>/` |

所有页面都在同一个域名下，所以“回到首页”就是 `/`，阅读记录（localStorage）全站共用。

## 一本书怎样接入

书仓库的 `.github/workflows/pages.yml` 只有一个 job：

```yaml
jobs:
  book:
    uses: AwesomeTechBooks/platform/.github/workflows/book.yml@v1
```

流水线（`.github/workflows/book.yml` → `tools/build-book.sh`）每次构建做四件事：

1. 用 mdBook 0.5.1 构建；现成 HTML 的书（Rust）写 `with: prebuilt: html`，原样复制。
2. 复制书根目录的 `LICENSE*`。版权页说许可证随书发布，缺了就构建失败。
3. 把 `reader/` 放进输出的 `_atb/reader/`，注入每个阅读页。
4. 对照 `components/` 的标准版本检查书里的副本，落后的报警告，不让构建失败。

仓库的 Settings → Pages → Source 要设为 “GitHub Actions”。
新书用 `tools/new-book.sh <书名> <标题>` 从 `template/` 生成骨架，再到入口仓库的 `catalog.json` 加一条。

## 共享的东西分两种

**站点外壳 `reader/`**：回到首页、调内容宽度、阅读记录和续读位置。它在构建时注入，书里不放副本，所以单独 `mdbook build` 一本书时没有这些功能。

**组件 `components/`**：书在自己的 `theme/` 里放一份副本，`book.toml` 照常引用，单独 `mdbook build` 也完整。
这里存的是标准版本。`tools/check-components.py <书目录>` 按文件名对照，`--sync` 把标准版本复制进书里。

| 组件 | 文件 | 作用 |
|---|---|---|
| `base` | `custom.css` | 图片白底、宽表格横向滚动 |
| `fig` | `fig.js`、`fig.css`、`fig_preprocess.py` | JSON 写的图（seq、grid、flow、chart），浏览器里画成可以逐步播放的 SVG；预处理器把 JSON 嵌进页面 |

只有一本书用的东西留在那本书里，例如 CUDA 书的统计图和分步动画、机器人书的公式预处理、CMake 书的副作用查看器。
等第二本书也要用了，再提到 `components/`。

## 版本

- 书仓库引用 `@v1`。`v1` 是移动的主版本标签，每次兼容的发布打 `v1.x.y`，再把 `v1` 移过去。
- 不兼容的改动发 `v2`，书逐本迁移。比如阅读器依赖的 mdBook 页面结构变了，就属于不兼容。
- 外壳和流水线改了以后，书要重新构建才生效：`tools/rebuild-all.sh` 用 `gh` 逐个触发书仓库的工作流。

## 本地预览整个站点

把各仓库克隆到同一个目录（工作区）下，然后：

```sh
platform/tools/build-site.sh <工作区> [输出目录]   # 默认输出到 <工作区>/_site
python3 -m http.server -d <工作区>/_site 8000       # 打开 http://localhost:8000/
```

它按 `catalog.json` 构建首页和每一本书，目录结构和线上一样。需要 PATH 上有 mdBook 0.5.1 和 `python3`。

## 各仓库通用的规矩

- **不收录商业书的原文和插图。** 原创教程即使参考了商业书，也必须是自己写的文字、自己画的图、自己写的代码。改编自开源文档的内容，在那本书的 README 和版权页写明出处。
- 每本书的许可证只管那本书。本仓库的代码是 MIT（`LICENSE`）。
- 仓库里不写服务器地址、密钥、个人信息、本机绝对路径。
- 示例的运行输出（`.out`、录制文件）由写作项目的脚本生成，不手改。
- 提交信息用 Conventional Commits 风格：`feat(reader): …`、`fix(fig): …`、`docs: …`。
