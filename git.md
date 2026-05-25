# Git 实战教程：从开源协作到内部流程

> **教程目标**：以 Easyparse 文件解析服务为案例，掌握 Git 在开源社区和企业内部的不同用法，包括 submodule / 本地依赖管理、仓库权限控制等高级话题。

---

## 目录

1. [基础概念回顾](#1-基础概念回顾)
2. [案例背景：Easyparse 文件解析服务](#2-案例背景easyparse-文件解析服务)
3. [开源协作流程](#3-开源协作流程)
4. [内部使用流程](#4-内部使用流程)
5. [Git Submodule 深度解析](#5-git-submodule-深度解析)
6. [仓库权限与可见性控制](#6-仓库权限与可见性控制)
7. [常规开发流程](#7-常规开发流程)
8. [常见问题与最佳实践](#8-常见问题与最佳实践)

---

## 1. 基础概念回顾

### 1.1 Git 核心概念速览

```
工作区 (Working Directory)
    │  git add
    ▼
暂存区 (Staging Area / Index)
    │  git commit
    ▼
本地仓库 (Local Repository)
    │  git push
    ▼
远程仓库 (Remote Repository)
```

### 1.2 关键概念

| 概念 | 说明 |
|------|------|
| **Commit** | 一次快照，记录文件在某一时刻的状态 |
| **Branch** | 指向某个 commit 的指针，用于并行开发 |
| **Tag** | 不可移动的commit指针，常用于标记发版 |
| **Remote** | 远程仓库的引用，如 `origin`、`upstream` |
| **HEAD** | 指向当前所在分支或 commit 的指针 |
| **Merge** | 将两个分支的历史合并到一起 |
| **Rebase** | 将当前分支的提交"移植"到另一个分支的顶端 |

### 1.3 基础命令速查

#### 一、仓库管理

| 命令 | 说明 |
|------|------|
| `git init` | 在当前目录初始化一个新的 Git 仓库（创建 `.git` 隐藏文件夹） |
| `git clone <仓库地址>` | 从远程服务器复制完整仓库到本地，例如 `git clone https://github.com/user/repo.git` |

#### 二、文件状态与追踪

| 命令 | 说明 |
|------|------|
| `git status` | 查看工作区文件的当前状态（已修改 / 暂存 / 未追踪） |
| `git add <文件名>` | 将文件从工作区添加到暂存区，支持通配符如 `git add .` 添加所有文件 |
| `git rm <文件名>` --cache | 从版本控制中删除文件（同时删除工作区文件） |

#### 三、提交与历史

| 命令 | 说明 |
|------|------|
| `git commit -m "提交说明"` | 将暂存区内容生成一个版本快照，`-m` 后跟提交描述 |
| `git log` | 查看提交历史记录（按时间倒序，显示作者、日期、SHA-1 哈希值） |
| `git log --oneline --graph --decorate` | 图形化查看历史 |
| `git diff` | 查看未暂存文件的修改对比，`--cached` 查看已暂存修改 |
| `git reflog` | 查看操作日志（救命用） |

#### 四、分支操作

| 命令 | 说明 |
|------|------|
| `git branch` | 列出本地分支（当前分支前有 `*` 标记） |
| `git branch -a` | 查看所有分支（含远程） |
| `git checkout -b <分支名>` | 创建并切换到新分支，等价于 `git branch <分支名>` + `git checkout <分支名>` |
| `git merge <分支名>` | 将指定分支的修改合并到当前分支 |
| `git merge --no-ff <branch>` | 强制创建合并提交（推荐） |
| `git rebase -i HEAD~3` | 交互式变基最近 3 次提交 |
| `git rebase --onto main featureA featureB` | 将 featureB 独有的提交移到 main |
| `git branch -d <branch>` | 删除本地分支 |

#### 五、远程协作

| 命令 | 说明 |
|------|------|
| `git remote -vv` | 查看当前仓库关联的所有远程仓库及其 URL |
| `git remote add <名称> <地址>` | 添加远程仓库，如 `git remote add origin https://github.com/user/repo.git` |
| `git remote set-url <名称> <地址>` | 修改远程仓库地址（如从 HTTPS 切换到 SSH：`git remote set-url origin git@github.com:user/repo.git`） |
| `git remote remove <名称>` | 删除远程仓库关联，如 `git remote remove upstream` |
| `git push origin <分支名>` | 将本地分支推送到远程仓库，如 `git push origin main` |
| `git push -u origin <分支名>` | 首次推送并建立追踪关系（`-u` = `--set-upstream`），之后只需 `git push` 即可 |
| `git pull origin <分支名>` | 拉取远程分支最新代码并合并到当前分支（等价于 `git fetch` + `git merge`） |
| `git push origin --delete <branch>` | 删除远程分支 |
| `git fetch --prune` | 清理已删除的远程分支引用 |

#### 六、撤销与回退

| 命令 | 说明 |
|------|------|
| `git reset --hard <提交ID>` | 强制回退到指定版本（**会丢弃该版本后的所有修改，谨慎使用**） |
| `git revert <提交ID>` | 通过创建新提交来撤销某次历史修改（**更安全，适合公共分支**） |

#### 七、Submodule

| 命令 | 说明 |
|------|------|
| `git submodule add <url> <path>` | 添加 submodule |
| `git submodule update --init --recursive` | 初始化所有 submodule |
| `git submodule update --remote` | 更新到远程最新 |
| `git submodule deinit <path>` | 移除 submodule |

#### 八、标签

| 命令 | 说明 |
|------|------|
| `git tag -a v1.0.0 -m "Release v1.0.0"` | 创建附注标签 |
| `git push origin --tags` | 推送所有标签 |
| `git tag -d v1.0.0` | 删除本地标签 |
| `git push origin --delete v1.0.0` | 删除远程标签 |

#### 九、其他实用命令

| 命令 | 说明 |
|------|------|
| `git stash` | 临时保存工作区未提交的修改（包括暂存区），恢复干净工作区 |
| `git stash list` | 查看所有 stash 记录列表 |
| `git stash pop` | 恢复最近一次 stash 的修改并删除该 stash 记录 |
| `git stash apply` | 恢复最近一次 stash 的修改但保留 stash 记录（可多次应用） |
| `git stash drop` | 删除最近一次 stash 记录 |
| `git stash clear` | 清空所有 stash 记录 |
| `git stash push -m "描述"` | 保存修改并添加描述信息，方便后续查找 |
| `git stash -u` | 保存时同时包含未被 Git 追踪的新文件（untracked files） |

> **典型场景**：正在开发 `feature/ofd-batch-convert` 分支，突然需要切换到 `fix/ofd-font-rendering` 紧急修复——用 `git stash` 暂存当前工作，切分支修复，回来再 `git stash pop` 恢复，无缝衔接。

---

## 2. 案例背景：Easyparse 文件解析服务

### 2.1 项目介绍

我们以 **Easyparse** 项目贯穿全教程——一个基于 FastAPI 的文件解析与转换服务。

- **主体服务**：`easyparse` — 文件解析与转换 Web 服务，支持 OFD → PDF、Markdown → Word、多格式文件 → 纯文本，Apache 2.0 协议开源在 GitHub
- **本地依赖**：`easyofd`（OFD 渲染）、`markitdown`（微软开源的文档解析库）— 以本地源码形式引入，类似 submodule 的依赖管理方式
- **自研模块**：`md2word` — Markdown → Word 转换引擎，以项目内置包形式存在

```
easyparse (GitHub 开源)                  
├── server.py           # FastAPI 入口   
├── routers/            # 路由层         
│   ├── convert.py      # 文件→文本      
│   ├── mdtoword.py     # MD→Word       
│   └── ofdtopdf.py     # OFD→PDF       
├── md2word/            # 自研模块       
│   ├── parser/         # MD 解析器      
│   ├── provider/       # DOCX 生成器    
│   └── config/         # 样式配置       
├── utils/              # 工具函数       
├── easyofd/            ← 本地依赖（OFD渲染）
├── markitdown/         ← 本地依赖（文档解析）
│                                        
└── LICENSE (Apache 2.0)                 
```

### 2.2 仓库清单

| 仓库名 | 可见性 | 托管平台 | 说明 |
|--------|--------|----------|------|
| `easyparse` | Public | GitHub | 文件解析与转换服务主体 |
| `easyofd` | Public | GitHub | OFD 解析渲染库（本地依赖） |
| `markitdown` | Public | GitHub | 微软文档解析库（本地依赖） |
| `md2word-config` | Limited | 行内 Gitea | 行内 Word 样式配置模板（仅登录用户可见） |

---

## 3. 开源协作流程

### 3.1 GitHub Flow 模型

开源社区最常用的协作模型，核心原则：

1. `main` 分支始终可部署
2. 所有新工作从 `main` 拉出 feature 分支
3. 通过 Pull Request 提交和审查代码
4. 合并后立即部署

```
main ───●───●───●───●───●───● (始终可发布)
         \         /
feature1  ●──●──●─┘
                   \      (PR + Code Review)
feature2            ●──●──┘
```

与之对比，行内采用严格的分支流水线，逐级向上合并：

```
main ───●─────────────────────●──── (生产，受严格保护)
        ↑                      ↑
release ●──────────────────────●──── (发布准备，uat 验收后合并)
        ↑                      ↑
uat     ●──────────────────────●──── (用户验收测试，sit 验证后合并)
        ↑                      ↑
sit      ●─────────────────────●──── (系统集成测试，开发起点)
        ↗                      ↖
feature ●──●──●               fix ●──● (功能/修复分支)
```



---

## 4. 内部使用流程

内部 Git 流程与开源有显著区别：更严格的权限控制、合规审查、变更管理。

### 4.1 分支模型（流水线，适用于 Gitea）

```
sit (系统集成测试)
  ↑
  ├── feature/ofd-batch-convert ──┐
  │   (开发 → 自测 → 提交到 sit)   │
  └── fix/md-table-parse ─────────┘
  │
uat (用户验收测试，sit 验证通过后合并)
  ↑
release (发布分支，uat 验收通过后合并)
  ↑
main (生产分支，受严格保护)

```

**流水线说明**：

| 阶段 | 环境 | 变更来源 | 合并方向 | 典型停留时间 |
|------|------|----------|----------|-------------|
| **sit** | 系统集成测试 | feature / fix 分支 | → uat | 1-3 天 |
| **uat** | 用户验收测试 | sit 分支 | → release | 3-5 天 |
| **release** | 发布准备 | uat 分支 | → main | 1-2 天 |
| **main** | 生产环境 | release 分支 | - | - |

### 4.2 分支策略细则

| 分支类型 | 命名规范 | 从哪拉出 | 合并到哪 | 谁可以推送 | 说明 |
|----------|----------|----------|----------|------------|------|
| `main` | main | - | - | 仅运维（Protected） | 生产环境，禁止直接推送 |
| `release` | release | uat | main | 技术负责人 | 发布分支，uat 验收通过后合并 |
| `uat` | uat | sit | release | 技术负责人 | 用户验收测试 |
| `sit` | sit | feature/fix | uat | 技术负责人 | 系统集成测试，开发成果集成点 |
| `feature/*` | feature/xxx | sit | sit | 开发者 | 功能开发分支 |
| `fix/*` | fix/xxx | sit | sit | 开发者 | Bug 修复分支 |
| `hotfix/*` | hotfix/xxx | main | main, 再向下同步 | 技术负责人 | 紧急生产修复 |

> **关键规则**：代码变更按照 **feature → sit → uat → release → main** 逐级向上合并，**绝不跳过任何阶段**。hotfix 是唯一例外，从 main 拉出，合并回 main 后需反向同步到 release、uat、sit。





### 4.4 仓库权限与分支保护矩阵（Gitea）

Gitea 的权限级别分为 **Owner → Admin → Write → Read → None** 五级，配合保护分支规则实现细粒度控制。

| 角色 | Gitea 权限 | main 分支 | release 分支 | uat 分支 | sit 分支 | feature 分支 | 创建 PR | 合并 PR |
|------|-----------|-----------|-------------|----------|----------|-------------|---------|---------|
| **开发者** | Write | ❌ 不可见 | ❌ 不可见 | ❌ 只读 | ❌ 只读 | ✅ 读写 | ✅ | ❌ |
| **技术负责人** | Admin | ❌ 只读 | ❌ 只读 | ✅ 可推送 | ✅ 可推送 | ✅ 读写 | ✅ | ✅（sit/uat） |
| **架构师/安全** | Read | ❌ 只读 | ❌ 只读 | ❌ 只读 | ❌ 只读 | ❌ 只读 | ❌ | ✅（审批） |
| **运维/DevOps** | Admin | ✅ 可推送 | ✅ 可推送 | ✅ 可推送 | ❌ 只读 | ❌ 只读 | ❌ | ✅（release/main） |

---

## 5. Git Submodule 深度解析

### 5.1 什么是 Submodule

Submodule 允许将一个 Git 仓库作为另一个 Git 仓库的子目录。常用于：
- 共享库的版本化管理
- 第三方依赖的源码引用
- 多项目间的代码复用

### 5.2 案例：Easyparse 引用 OFD 渲染库

```
easyparse/                  ← 主仓库（私有）
├── server.py
├── routers/
├── libs/
│   ├── easyofd/                 ← submodule，指向 easyofd 仓库的某个 commit
│   │   ├── ofd.py        # OFD 解析核心
│   │   ├── render.py     # PDF 渲染引擎
│   │   └── font/         # 字体资源
│   └── markitdown/              ← submodule，指向 markitdown 仓库的某个 commit
│       ├── pdf/          # PDF 文本提取
│       ├── docx/         # Word 文本提取
│       └── pptx/         # PPT 文本提取
└── .gitmodules                  ← submodule 配置文件
```

### 5.3 Submodule 完整操作指南

#### 5.3.1 添加 Submodule

```bash
# 进入主仓库
cd easyparse

# 添加 submodule（指定路径和分支）
git submodule add https://github.com/renoyuan/easyofd.git libs/easyofd
git submodule add -b v1.2-stable https://github.com/renoyuan/easyofd.git libs/easyofd

# .gitmodules 文件会自动生成：
# [submodule "libs/easyofd"]
#     path = libs/easyofd
#     url = https://github.com/renoyuan/easyofd.git
#     branch = v1.2-stable

# 提交 submodule 的引用
git add .gitmodules libs/easyofd
git commit -m "chore: add easyofd as submodule"
```

#### 5.3.2 克隆包含 Submodule 的仓库

```bash
# 方法一：克隆时同时初始化 submodule
git clone --recurse-submodules git@github.com:zhangler1/easyparse.git

# 方法二：先克隆，再初始化
git clone git@github.com:zhangler1/easyparse.git
cd bank-easyparse
git submodule init          # 初始化本地配置
git submodule update        # 拉取 submodule 内容

# 方法三：一步完成
git submodule update --init --recursive
```

#### 5.3.3 更新 Submodule

```bash
# 情况 1：submodule 远程有更新，拉到 submodule 所在分支的最新 commit
cd libs/easyofd
git fetch
git merge origin/v1.2-stable   # 或 git pull
cd ../..
git add libs/easyofd
git commit -m "chore: update easyofd to v1.2.3"

# 情况 2：直接让 submodule 跟踪远程分支的最新提交
git submodule update --remote libs/easyofd

# 情况 3：更新所有 submodule
git submodule update --remote --recursive
```

#### 5.3.4 在 Submodule 中开发

```bash
# 进入 submodule 目录
cd libs/easyofd

# 创建分支进行开发
git checkout -b fix/ofd-font-rendering

# 修改代码、提交
git add .
git commit -m "fix(render): fix font fallback for rare Chinese characters"
git push origin fix/ofd-font-rendering

# 回到主仓库，更新 submodule 引用
cd ../..
git add libs/easyofd
git commit -m "chore: update easyofd submodule (fix font rendering)"

# ⚠️ 注意：主仓库只记录 submodule 的 commit SHA，
# 不记录 submodule 的代码内容！
```

#### 5.3.5 移除 Submodule

```bash
# Git 1.8.5+ 推荐方式
git submodule deinit -f libs/easyofd
rm -rf .git/modules/libs/easyofd
git rm -f libs/easyofd

# 确认 .gitmodules 中相关配置已被移除
cat .gitmodules
```

### 5.4 Submodule 陷阱与最佳实践

#### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `detached HEAD` | submodule 默认处于分离头指针状态 | `cd submodule && git checkout <branch>` |
| 忘记更新 submodule | 切换分支后 submodule 未同步 | `git submodule update --init --recursive` |
| 主仓库记录旧 commit | 只在 submodule 中提交，忘记在主仓库更新引用 | 在主仓库 `git add <submodule>` 并提交 |
| 合并冲突 | 多人同时修改 submodule 引用 | 手动解决 .gitmodules 和 submodule commit 冲突 |

#### 最佳实践

```bash
# 1. 始终让 submodule 跟踪一个具体分支
git config -f .gitmodules submodule.libs/easyofd.branch v1.2-stable

# 2. 设置全局自动更新
git config --global submodule.recurse true
#git pull
# 以前：只更新父仓库，子模块不动
# 现在：自动更新子模块到正确版本
# git checkout
# 以前：切分支后子模块版本不匹配
# 现在：自动把子模块切到对应版本
# git push
# 自动检查子模块是否有未推送的提交
# 避免 “父仓库提交了，但子模块代码没推上去” 的坑

# 3. 使用 alias 简化操作
git config --global alias.sync-sub '!git submodule update --init --recursive && git submodule update --remote --recursive'
# 什么时候必须加 --init？
# 只在 第一次拉项目、第一次用子模块 时需要。第一次下载代码
#第一次只写 update = 白跑一趟，代码下不下来。
```

---

## 6. 仓库权限与可见性控制

### 6.1 仓库可见性级别

#### GitHub 可见性

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| **Public** | 任何人可见，任何人可克隆 | 开源项目 |
| **Internal** | 组织内所有人可见（GitHub Enterprise） | 公司内部工具 |
| **Private** | 仅被邀请的成员可见 | 商业项目、项目 |

#### Gitea 可见性（行内仓库用）

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| **Public** | 任何人可访问，无需登录 | 对外文档 |
| **Private** | 仅项目成员可访问 | 业务代码、核心系统 |

> **提示**：Gitea 的 `Limited` 相当于 GitLab 的 `Internal`，适合组织级别的内部共享。

### 6.2 仓库分级策略

```
┌──────────────────────────────────────────────────┐
│                    Git 仓库分级                │
├─────────────┬────────────────┬───────────────────┤
│   密级       │   可见性        │   仓库示例         │
├─────────────┼────────────────┼───────────────────┤
│  公开        │ Public         │ 开源 SDK、技术博客  │
│  内部        │ Limited        │ 共享组件库、工具    │
│  受限        │ Private (团队A)│ 特定业务模块        │
│  绝密        │ Private + IP   │ 密钥管理风控规则    │
│             │ 白名单          │                   │
└─────────────┴────────────────┴───────────────────┘
```


### 6.4 仓库级权限矩阵（Gitea）

Gitea 的仓库权限更简洁，分为五级：


| 权限级别 | 角色 | 查看代码 | 创建分支 | 推送代码 | 创建 PR | 合并 PR | 管理仓库 |
|----------|------|----------|----------|----------|---------|---------|----------|
| **Owner** | 项目所有者 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Admin** | 技术负责人 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅（不含转移所有权） |
| **Write** | 开发工程师 | ✅ | ✅ | ✅ (非保护分支) | ✅ | ❌ | ❌ |
| **Read** | PM、QA、安全审计 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **None** | 无权限 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

---


## 7. 常规开发流程

```bash
# ─── 社区开发者  的操作 ───

# 1. Fork 仓库
# GitHub 网页：fork renoyuan/easyofd → xiaowang/easyofd

# 2. 克隆并配置
git clone https://github.com/xiaowang/easyofd.git
cd easyofd
git remote add upstream https://github.com/renoyuan/easyofd.git

# 3. 创建功能分支
git checkout -b feat/annot-support
# 编写代码：annot_parser.py, test_annot_parser.py

# 4. 提交
git add .
git commit -m "feat(parser): add OFD annotation comment support"

# 5. 同步上游并推送
git fetch upstream
git rebase upstream/main
git push origin feat/annot-support

# 6. 创建 Pull Request（GitHub 网页操作）
# base: renoyuan/easyofd main
# compare: xiaowang/easyofd feat/annot-support
```

---

## 8. 常见问题与最佳实践

### 8.1 Git 规范清单

```markdown
## ☑ 必须遵守

- [ ] release / main 全部配置为保护分支
- [ ] 禁止直接推送到 release / main 分支
- [ ] Commit message 必须包含CQ单号
- [ ] 代码严格按 sit → uat → release → main 逐级合并，不得跳级
- [ ] 合并方式统一使用 --no-ff（保留合并轨迹）

## ☑ 建议遵守

- [ ] Submodule 固定到具体 tag，不跟踪 branch
- [ ] 定期同步上游开源仓库（如 easyofd、markitdown 的新版本）
- [ ] 敏感文件加入 .gitignore（密钥、证书、环境变量文件）
- [ ] 定期审计仓库成员权限
- [ ] hotfix 合并到 main 后，反向同步到 release → uat → sit
- [ ] 本地依赖（如 easyofd/markitdown）锁定到经过验证的 commit，避免盲目追新
```

### 8.2 Submodule 决策树

```
需要共享代码？
├── 是独立维护的通用库？
│   └── ✅ 使用 Submodule，引用具体 tag
│
├── 是第三方代码，需要偶尔改？
│   └── ✅ 使用 Submodule + fork 到内部仓库
│
├── 是第三方代码，完全不改？
│   └── ❌ 用包管理器（npm, pip, maven）
│
└── 是项目内部代码，需要深度定制？
    └── ❌ 直接放到项目目录，或用 Monorepo
```

---

## 附录：环境搭建

### A. Git 基础配置

```bash
# 全局用户信息
git config --global user.name "张三"
git config --global user.email "zhangsan@bank.com"

# 常用别名
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.st status
git config --global alias.lg "log --oneline --graph --decorate --all -20"

# 设置默认分支名
git config --global init.defaultBranch main

# 设置推送行为
git config --global push.default simple
git config --global pull.rebase true     # pull 时默认变基

# 代理配置（如需要）
git config --global http.proxy http://proxy.bank.com:8080
git config --global https.proxy http://proxy.bank.com:8080
```

### B. SSH 密钥配置

```bash
# 生成 SSH 密钥
ssh-keygen -t ed25519 -C "zhangsan@bank.com"


# 公钥添加到 Gitea/GitHub
cat ~/.ssh/id_ed25519.pub
# 复制输出内容 → Gitea 个人设置 → SSH/GPG Keys → Add SSH Key
# GitHub → Settings → SSH and GPG Keys
```

---
