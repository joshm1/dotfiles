-- Minimal Neovim Config with native package system
-- Josh's clean setup - 2025-10-19

-- Basic settings
vim.opt.number = true         -- Line numbers
vim.opt.relativenumber = true -- Relative line numbers
vim.opt.mouse = 'a'           -- Enable mouse
vim.opt.ignorecase = true     -- Case insensitive search
vim.opt.smartcase = true      -- Unless uppercase is used
vim.opt.hlsearch = true       -- Highlight search results
vim.opt.wrap = false          -- Don't wrap lines
vim.opt.breakindent = true    -- Preserve indentation in wrapped text
vim.opt.tabstop = 2           -- Tabs are 2 spaces
vim.opt.shiftwidth = 2        -- Indent with 2 spaces
vim.opt.expandtab = true      -- Use spaces instead of tabs
vim.opt.termguicolors = true  -- True color support
vim.opt.signcolumn = 'yes'    -- Always show sign column
vim.opt.updatetime = 250      -- Faster completion
vim.opt.timeoutlen = 300      -- Faster key sequence completion
vim.opt.splitbelow = true     -- Horizontal splits go below
vim.opt.splitright = true     -- Vertical splits go right

-- Set leader key to space
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- Basic keymaps
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>') -- Clear search highlight
vim.keymap.set('i', 'jk', '<ESC>')                  -- jk to escape
vim.keymap.set('n', ';', ':', { desc = 'Command mode' })

-- Diagnostic keybindings (global)
vim.keymap.set('n', '<leader>e', vim.diagnostic.open_float, { desc = 'Show diagnostic float' })
vim.keymap.set('n', '[d', vim.diagnostic.goto_prev, { desc = 'Previous diagnostic' })
vim.keymap.set('n', ']d', vim.diagnostic.goto_next, { desc = 'Next diagnostic' })

-- Install plugins (vim.pack is native to Neovim 0.12+)
vim.pack.add({
  { src = 'https://github.com/christoomey/vim-tmux-navigator' },
  { src = 'https://github.com/catppuccin/nvim' },
  { src = 'https://github.com/neovim/nvim-lspconfig' },
  { src = 'https://github.com/nvim-lua/plenary.nvim' },  -- Required by telescope
  { src = 'https://github.com/nvim-telescope/telescope.nvim' },
  { src = 'https://github.com/hrsh7th/nvim-cmp' },       -- Completion engine
  { src = 'https://github.com/hrsh7th/cmp-nvim-lsp' },   -- LSP completion source
  { src = 'https://github.com/hrsh7th/cmp-buffer' },     -- Buffer completion source
  { src = 'https://github.com/hrsh7th/cmp-path' },       -- Path completion source
})

-- Set colorscheme
vim.cmd.colorscheme('catppuccin-frappe') -- frappe variant

-- LSP Diagnostics Configuration
vim.diagnostic.config({
  virtual_text = {
    spacing = 4,
    prefix = '●',
    -- Show full message without truncation
    source = 'if_many', -- Show source like [basedpyright]
  },
  signs = true,         -- Show signs in gutter
  underline = true,     -- Underline errors
  update_in_insert = false,
  severity_sort = true,
  float = {
    border = 'rounded',
    source = 'always', -- Always show source in floating window
    header = '',
    prefix = '',
  },
})

-- LSP keybindings (set when LSP attaches to buffer)
vim.api.nvim_create_autocmd('LspAttach', {
  group = vim.api.nvim_create_augroup('UserLspConfig', {}),
  callback = function(ev)
    local opts = { buffer = ev.buf }
    vim.keymap.set('n', 'gd', vim.lsp.buf.definition, opts)                                     -- Go to definition
    vim.keymap.set('n', 'gD', vim.lsp.buf.declaration, opts)                                    -- Go to declaration
    vim.keymap.set('n', 'gr', vim.lsp.buf.references, opts)                                     -- Show references
    vim.keymap.set('n', 'gi', vim.lsp.buf.implementation, opts)                                 -- Go to implementation
    vim.keymap.set('n', 'K', vim.lsp.buf.hover, opts)                                           -- Hover documentation
    vim.keymap.set('n', '<leader>e', vim.diagnostic.open_float, opts)                           -- Show full error in float
    vim.keymap.set('n', '<leader>rn', vim.lsp.buf.rename, opts)                                 -- Rename symbol
    vim.keymap.set('n', '<leader>ca', vim.lsp.buf.code_action, opts)                            -- Code actions
    vim.keymap.set('n', '[d', vim.diagnostic.goto_prev, opts)                                   -- Previous diagnostic
    vim.keymap.set('n', ']d', vim.diagnostic.goto_next, opts)                                   -- Next diagnostic
    vim.keymap.set('n', '<leader>f', function() vim.lsp.buf.format({ async = true }) end, opts) -- Format
  end,
})

-- LSP
vim.lsp.config('basedpyright', {
  root_markers = {
    'uv.lock',                                           -- Prioritize uv workspace root
    unpack(vim.lsp.config['basedpyright'].root_markers), -- Keep defaults
  },
  settings = {
    basedpyright = {
      analysis = {
        diagnosticMode        = "workspace",
        autoImportCompletions = true,
        autoSearchPaths       = true,
        -- typeCheckingMode = "strict",
        inlayHints            = {
          callArgumentNames = true
        }
      }
    }
  }
})
vim.lsp.enable('basedpyright')

-- Ruff LSP - inherits settings from pyproject.toml
-- Disable ruff diagnostics to avoid conflicts with basedpyright
-- vim.lsp.config('ruff', {
-- })
vim.lsp.enable('ruff')

-- Lua LSP - for Neovim config development
vim.lsp.config('lua_ls', {
  settings = {
    Lua = {
      runtime = {
        version = 'LuaJIT', -- Neovim uses LuaJIT
      },
      diagnostics = {
        globals = { 'vim' }, -- Recognize 'vim' global
      },
      workspace = {
        library = vim.api.nvim_get_runtime_file("", true), -- Make server aware of Neovim runtime files
        checkThirdParty = false,                           -- Don't ask about luassert, busted, etc.
      },
      telemetry = {
        enable = false, -- Don't send telemetry
      },
    },
  },
})
vim.lsp.enable('lua_ls')

-- nvim-cmp setup
local cmp = require('cmp')
cmp.setup({
  window = {
    documentation = cmp.config.window.bordered(), -- Show type info window
  },
  mapping = cmp.mapping.preset.insert({
    ['<C-b>'] = cmp.mapping.scroll_docs(-4),
    ['<C-f>'] = cmp.mapping.scroll_docs(4),
    ['<C-Space>'] = cmp.mapping.complete(), -- Manually trigger completion
    ['<C-e>'] = cmp.mapping.abort(),
    ['<CR>'] = cmp.mapping.confirm({ select = true }),
    ['<Tab>'] = cmp.mapping.select_next_item(),
    ['<S-Tab>'] = cmp.mapping.select_prev_item(),
  }),
  sources = cmp.config.sources({
    { name = 'nvim_lsp' },
    { name = 'buffer' },
    { name = 'path' },
  }),
  formatting = {
    format = function(entry, vim_item)
      -- Show source of completion
      vim_item.menu = ({
        nvim_lsp = '[LSP]',
        buffer = '[Buffer]',
        path = '[Path]',
      })[entry.source.name]
      return vim_item
    end,
  },
})

-- Format on save with ruff
vim.api.nvim_create_autocmd('BufWritePre', {
  pattern = '*.py',
  callback = function()
    vim.lsp.buf.format({ async = false })
  end,
})

-- Format on save for Lua files
vim.api.nvim_create_autocmd('BufWritePre', {
  pattern = '*.lua',
  callback = function()
    vim.lsp.buf.format({ async = false })
  end,
})

-- Telescope keybindings
local telescope_builtin = require('telescope.builtin')
vim.keymap.set('n', '<leader>ff', telescope_builtin.find_files, { desc = 'Find files' })
vim.keymap.set('n', '<leader>fg', telescope_builtin.live_grep, { desc = 'Live grep' })
vim.keymap.set('n', '<leader>fb', telescope_builtin.buffers, { desc = 'Find buffers' })
vim.keymap.set('n', '<leader>fh', telescope_builtin.help_tags, { desc = 'Help tags' })
vim.keymap.set('n', '<leader>fr', telescope_builtin.oldfiles, { desc = 'Recent files' })
