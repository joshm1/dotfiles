let g:python_host_prog = '/Users/josh/.pyenv/versions/neovim2/bin/python'
let g:python3_host_prog = '/Users/josh/.pyenv/versions/neovim3/bin/python'

let mapleader = "\<Space>"
set foldmethod=manual       " use manual folding
set background=dark

" Autoinstall vim-plug {{{
if empty(glob('~/.nvim/autoload/plug.vim'))
  silent !curl -fLo ~/.nvim/autoload/plug.vim --create-dirs
    \ https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
  autocmd VimEnter * PlugInstall
endif
" }}}

call plug#begin()

" Appearance
Plug 'itchyny/lightline.vim'

Plug 'nanotech/jellybeans.vim'
" {{{ colortheme https://github.com/junegunn/seoul256.vim
let g:jellybeans_use_term_background_color = 1
" }}}

Plug 'junegunn/seoul256.vim'
" {{{ colortheme https://github.com/junegunn/seoul256.vim
let g:seoul256_background = 233
" }}}

Plug 'ntpeters/vim-better-whitespace'
autocmd BufWritePre * StripWhitespace

Plug 'junegunn/vim-easy-align'

Plug 'tpope/vim-fugitive'
Plug 'airblade/vim-gitgutter'
Plug 'qpkorr/vim-bufkill'
Plug 'wellle/targets.vim'
Plug 'tpope/vim-eunuch'
Plug 'tpope/vim-ragtag'
Plug 'tpope/vim-rails'
Plug 'kchmck/vim-coffee-script'
Plug 'leafgarland/typescript-vim'

Plug 'scrooloose/syntastic'
" {{{ syntastic config
let g:syntastic_enable_signs          = 1
let g:syntastic_enable_highlighting   = 1
let g:syntastic_cpp_check_header      = 1
let g:syntastic_enable_balloons       = 1
let g:syntastic_echo_current_error    = 1
let g:syntastic_check_on_wq           = 0
let g:syntastic_error_symbol          = '✘'
let g:syntastic_warning_symbol        = '!'
let g:syntastic_style_error_symbol    = ':('
let g:syntastic_style_warning_symbol  = ':('
let g:syntastic_vim_checkers          = ['vint']
let g:syntastic_elixir_checkers       = ['elixir']
let g:syntastic_python_checkers       = ['flake8']
let g:syntastic_javascript_checkers   = ['eslint']
let g:syntastic_enable_elixir_checker = 0
let g:syntastic_always_populate_loc_list = 1

" suggested by vim-go
let g:syntastic_go_checkers = ['golint', 'govet', 'errcheck']
let g:syntastic_mode_map = { 'mode': 'active', 'passive_filetypes': ['go'] }

" }}}

Plug 't9md/vim-choosewin'
" {{{ vim-choosewin invoke with '-'
nmap  -  <Plug>(choosewin)
" }}}

Plug 'nathanaelkane/vim-indent-guides'
" {{{ https://github.com/nathanaelkane/vim-indent-guides
" toggle with <leader>ig
let g:indent_guides_auto_colors = 1
let g:indent_guides_enable_on_vim_startup = 1
" }}}

Plug 'nsf/gocode', { 'rtp': 'nvim', 'do': '~/.config/nvim/plugged/gocode/nvim/symlink.sh' }

Plug 'Shougo/deoplete.nvim', { 'do': ':UpdateRemotePlugins' }
" {{{ deoplete
" Plug 'zchee/deoplete-jedi' " python completion
" Plug 'zchee/deoplete-go', { 'do': 'make' }
Plug 'carlitux/deoplete-ternjs' " javascript completion
" Plug 'mhartington/deoplete-typescript'
let g:deoplete#enable_at_startup = 1
let g:deoplete#enable_ignore_case = 1
let g:deoplete#enable_smart_case = 1

" }}}

Plug 'osyo-manga/vim-monster' " {{{
let g:monster#completion#rcodetools#backend = "async_rct_complete"
let g:neocomplete#sources#omni#input_patterns = {
\   "ruby" : '[^. *\t]\.\w*\|\h\w*::',
\}
let g:monster#completion#rcodetools#backend = "async_rct_complete"
let g:deoplete#sources#omni#input_patterns = {
\   "ruby" : '[^. *\t]\.\w*\|\h\w*::',
\}
"}}}

Plug 'zchee/deoplete-go', { 'do': 'make'} " {{{
let g:deoplete#sources#go#gocode_binary = '~/.gotools/gocode'
" }}}

Plug '/usr/local/opt/fzf' | Plug 'junegunn/fzf.vim' " {{{
let g:fzf_commits_log_options = '--graph --color=always --format="%C(auto)%h%d %s %C(black)%C(bold)%cr"'

" Advanced customization using autoload functions
autocmd VimEnter * command! Colors
  \ call fzf#vim#colors({'left': '15%', 'options': '--reverse --margin 30%,0'})

nnoremap <silent> <leader><space> :Files<CR>
nnoremap <silent> <leader>a :Buffers<CR>
nnoremap <silent> <leader>A :Windows<CR>
nnoremap <silent> <leader>; :BLines<CR>
nnoremap <silent> <leader>. :Lines<CR>
nnoremap <silent> <leader>o :BTags<CR>
nnoremap <silent> <leader>O :Tags<CR>
nnoremap <silent> <leader>? :History<CR>
nnoremap <silent> <leader>/ :execute 'Ag ' . input('Ag/')<CR>
nnoremap <silent> K :call SearchWordWithAg()<CR>
vnoremap <silent> K :call SearchVisualSelectionWithAg()<CR>
nnoremap <silent> <leader>gl :Commits<CR>
nnoremap <silent> <leader>ga :BCommits<CR>

imap <C-x><C-f> <plug>(fzf-complete-file-ag)
imap <C-x><C-l> <plug>(fzf-complete-line)

function! SearchWordWithAg()
  execute 'Ag' expand('<cword>')
endfunction

function! SearchVisualSelectionWithAg() range
  let old_reg = getreg('"')
  let old_regtype = getregtype('"')
  let old_clipboard = &clipboard
  set clipboard&
  normal! ""gvy
  let selection = getreg('"')
  call setreg('"', old_reg, old_regtype)
  let &clipboard = old_clipboard
  execute 'Ag' selection
endfunction
" }}}

Plug 'thoughtbot/vim-rspec' " {{{
map <Leader>t :call RunCurrentSpecFile()<CR>
map <Leader>s :call RunNearestSpec()<CR>
map <Leader>l :call RunLastSpec()<CR>
" }}}

" File Navigation
" ====================================================================
Plug 'scrooloose/nerdtree'
" {{{ NERDtree
let g:NERDTreeMinimalUI = 1
let g:NERDTreeHijackNetrw = 0
let g:NERDTreeWinSize = 31
let g:NERDTreeChDirMode = 2
let g:NERDTreeAutoDeleteBuffer = 1
let g:NERDTreeShowBookmarks = 1
let g:NERDTreeCascadeOpenSingleChildDir = 1
let g:NERDTreeIgnore=['\.sw?$', '\~$']

" close vim if the only window left open is NERDTree
autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif

map <F1> :call NERDTreeToggleAndFind()<cr>
map <F2> :NERDTreeToggle<CR>

function! NERDTreeToggleAndFind()
  if (exists('t:NERDTreeBufName') && bufwinnr(t:NERDTreeBufName) != -1)
    execute ':NERDTreeClose'
  else
    execute ':NERDTreeFind'
  endif
endfunction
" }}}

Plug 'danchoi/ruby_bashrockets.vim'

Plug 'fatih/vim-go'
" {{{
let g:go_list_type = "quickfix"

au FileType go nmap <leader>rt <Plug>(go-run-tab)
au FileType go nmap <Leader>rs <Plug>(go-run-split)
au FileType go nmap <Leader>rv <Plug>(go-run-vertical)

" Open definition/declaration
au FileType go nmap <Leader>ds <Plug>(go-def-split)
au FileType go nmap <Leader>dv <Plug>(go-def-vertical)
au FileType go nmap <Leader>dt <Plug>(go-def-tab)

" Open the relevant Godoc for the word under the cursor with <leader>gd or open it vertically with <leader>gv<Paste>
au FileType go nmap <Leader>gd <Plug>(go-doc)
au FileType go nmap <Leader>gv <Plug>(go-doc-vertical)

" Or open the Godoc in browser
au FileType go nmap <Leader>gb <Plug>(go-doc-browser)

" Show a list of interfaces which is implemented by the type under your cursor
au FileType go nmap <Leader>s <Plug>(go-implements)

" Show type info for the word under your cursor
au FileType go nmap <Leader>i <Plug>(go-info)

let g:go_highlight_functions = 1
let g:go_highlight_methods = 1
let g:go_highlight_fields = 1
let g:go_highlight_structs = 1
let g:go_highlight_interfaces = 1
let g:go_highlight_operators = 1
let g:go_highlight_build_constraints = 1

" Enable goimports to automatically insert import paths instead of gofmt
let g:go_fmt_command = "goimports"
" }}}

Plug 'Shougo/neosnippet.vim' " {{{
" Plugin key-mappings.
imap <C-k>     <Plug>(neosnippet_expand_or_jump)
smap <C-k>     <Plug>(neosnippet_expand_or_jump)
xmap <C-k>     <Plug>(neosnippet_expand_target)
" }}}

Plug 'Shougo/neosnippet-snippets'

" Plug 'ajh17/VimCompletesMe'

call plug#end()

set wildignore+=*/tmp/*,*.so,*.swp,*.zip,*/.git/*,*/.hg/*,*/.svn/*,*/.idea/*,*/.DS_Store,*/vendor
set nowrap
set colorcolumn=110
colo jellybeans " jellybeans or seoul256

set tabstop=2 shiftwidth=2 sts=2
set expandtab
set number

autocmd FileType yaml :set foldmethod=indent foldminlines=10 foldlevel=4

nnoremap <leader>- <C-w>s<C-w>j


noremap <silent> <F4> :let @+=expand("%:p")<CR>

" navigate splits {{{
nmap <c-h> <c-w>h
nmap <c-j> <c-w>j
nmap <c-k> <c-w>k
nmap <c-l> <c-w>l
" }}}

nmap <c-.> :bn<CR>
nmap <c-,> :bp<CR>

" do not beep {{{
set noerrorbells visualbell t_vb=
autocmd GUIEnter * set visualbell t_vb=
" }}}

" {{{ copy/paste helpers
" paste w/ noindent
" nmap <silent> <leader>p :set paste<CR>"*p:set nopaste<CR>

" Copy to clipboard
vnoremap  <leader>y  "+y
nnoremap  <leader>Y  "+yg_
nnoremap  <leader>y  "+y
nnoremap  <leader>yy  "+yy

" Paste from clipboard
nnoremap <leader>p "+p
nnoremap <leader>P "+P
vnoremap <leader>p "+p
vnoremap <leader>P "+P
" }}}

" Universal closing behavior
nnoremap <silent> Q :call CloseSplitOrDeleteBuffer()<CR>
function! CloseSplitOrDeleteBuffer() " {{{
  if winnr('$') > 1
    wincmd c
  else
    execute 'bdelete'
  endif
endfunction " }}}

" Make directory under current file if it doesn't exit
function! s:MkNonExDir(file, buf) " {{{
  " source: http://stackoverflow.com/questions/4292733/vim-creating-parent-directories-on-save
  if empty(getbufvar(a:buf, '&buftype')) && a:file!~#'\v^\w+\:\/'
    let dir=fnamemodify(a:file, ':h')
    if !isdirectory(dir)
      call mkdir(dir, 'p')
    endif
  endif
endfunction
augroup BWCCreateDir
  autocmd!
  autocmd BufWritePre * :call s:MkNonExDir(expand('<afile>'), +expand('<abuf>'))
augroup END
" }}}


" vim: set sw=2 ts=2 et foldlevel=0 foldmethod=marker:
