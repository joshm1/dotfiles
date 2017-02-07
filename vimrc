set nocompatible              " be iMproved, required
filetype off                  " required

" set the runtime path to include Vundle and initialize
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()

" let Vundle manage Vundle, required
Plugin 'gmarik/Vundle.vim'

Plugin 'tpope/vim-fugitive'
Plugin 'Valloric/YouCompleteMe'
Plugin 'scrooloose/syntastic'
Plugin 'kien/ctrlp.vim'
Plugin 'rking/ag.vim'
Plugin 'tpope/vim-sensible'
Plugin 'scrooloose/nerdtree'
Plugin 'Xuyuanp/nerdtree-git-plugin'
Plugin 'tpope/vim-surround'
Plugin 'tpope/vim-repeat'
Plugin 'altercation/vim-colors-solarized'
Plugin 'bling/vim-airline'
Plugin 'scrooloose/nerdcommenter'
Plugin 'pangloss/vim-javascript'
Plugin 'tpope/vim-rails'
Plugin 'airblade/vim-gitgutter'
Plugin 'ntpeters/vim-better-whitespace'
Plugin 'mattn/emmet-vim'
Plugin 'matchit.zip'
Plugin 'ludovicchabant/vim-gutentags'
Plugin 'dyng/ctrlsf.vim'
Plugin 'qpkorr/vim-bufkill'
Plugin 'tpope/vim-eunuch' " https://github.com/tpope/vim-eunuch
Plugin 'fatih/vim-go'

" rust
" Plugin 'rust-lang/rust.vim'
" Plugin 'cespare/vim-toml' " TOML

" php
" Plugin 'StanAngeloff/php.vim'
" Plugin '2072/PHP-Indenting-for-VIm'

" misc
" Plugin 'burnettk/vim-angular'
" Plugin 'chase/vim-ansible-yaml'

" All of your Plugins must be added before the following line
call vundle#end()            " required
filetype plugin indent on    " required

" To ignore plugin indent changes, instead use:
"filetype plugin on
"
" Brief help
" :PluginList       - lists configured plugins
" :PluginInstall    - installs plugins; append `!` to update or just :PluginUpdate
" :PluginSearch foo - searches for foo; append `!` to refresh local cache
" :PluginClean      - confirms removal of unused plugins; append `!` to auto-approve removal
"
" see :h vundle for more details or wiki for FAQ
" Put your non-Plugin stuff after this line

let mapleader = ","
set wildignore+=*/tmp/*,*.so,*.swp,*.zip,*/.git/*,*/.hg/*,*/.svn/*,*/.idea/*,*/.DS_Store,*/vendor
set background=dark
colorscheme solarized
set nowrap
set colorcolumn=110

set tabstop=2 shiftwidth=2 sts=2
set expandtab
set number

" navigate splits
map <c-h> <c-w>h
map <c-j> <c-w>j
map <c-k> <c-w>k
map <c-l> <c-w>l

nnoremap <leader>- <C-w>s<C-w>j

" kill buffer without closing split
map Q :BD<CR>
nmap <c-.> :bn<CR>
nmap <c-,> :bp<CR>

" do not beep
set noerrorbells visualbell t_vb=
autocmd GUIEnter * set visualbell t_vb=

" auto remove trailing whitespace
autocmd BufWritePre * :%s/\s\+$//e

" paste w/ noindent
nmap <silent> <leader>p :set paste<CR>"*p:set nopaste<CR>

"
" Syntastic
"

set statusline+=%#warningmsg#
set statusline+=%{SyntasticStatuslineFlag()}
set statusline+=%*

let g:syntastic_always_populate_loc_list = 1
let g:syntastic_auto_loc_list = 1
let g:syntastic_check_on_open = 1
let g:syntastic_check_on_wq = 0

"
" ctrlp / https://github.com/kien/ctrlp.vim
"

let g:ctrlp_map = '<leader>t'
let g:ctrlp_working_path_mode = 'a'
let g:ctrlp_custom_ignore = {
  \ 'dir':  '\v[\/]\.(git|hg|svn|node_modules|bower_components|managed-lib|dist|build|vendor)$',
  \ 'file': '\v\.(exe|so|dll)$',
  \ 'link': 'some_bad_symbolic_links',
  \ }

" The Silver Searcher
if executable('ag')
  " Use ag over grep
  set grepprg=ag\ --nogroup\ --nocolor

  " Use ag in CtrlP for listing files. Lightning fast and respects .gitignore
  let g:ctrlp_user_command = 'ag %s -l --nocolor -g ""'

  " ag is fast enough that CtrlP doesn't need to cache
  let g:ctrlp_use_caching = 0
endif

map <leader>b :CtrlPBuffer<CR>
map <leader>m :CtrlPMRUFiles<CR>

"
" ag.vim / https://github.com/rking/ag.vim
"

nnoremap \ :Ag!<SPACE>

"
" NERDTree
"

" open a NERDTree automatically when vim starts up if no files were specified
autocmd StdinReadPre * let s:std_in=1
autocmd VimEnter * if argc() == 0 && !exists("s:std_in") | NERDTree | endif

map <leader>n :NERDTreeToggle<CR>

"
" vim-airline / https://github.com/bling/vim-airline
"
let g:airline#extensions#tabline#enabled = 1

"
" ctrlsf / https://github.com/dyng/ctrlsf.vim
"

nmap     <C-F>f <Plug>CtrlSFPrompt
vmap     <C-F>f <Plug>CtrlSFVwordPath
vmap     <C-F>F <Plug>CtrlSFVwordExec
nmap     <C-F>n <Plug>CtrlSFCwordPath
nmap     <C-F>p <Plug>CtrlSFPwordPath
nnoremap <C-F>o :CtrlSFOpen<CR>
nnoremap <C-F>t :CtrlSFToggle<CR>
inoremap <C-F>t <Esc>:CtrlSFToggle<CR>

"
" GitGutter
"
nnoremap <leader>u :GitGutterNextHunk<CR>
nnoremap <leader>y :GitGutterPrevHunk<CR>
nnoremap <leader>s :GitGutterStageHunk<CR>

"
" Emmet
"

let g:user_emmet_mode='inv'  " enable all functions
let g:user_emmet_install_global = 0 " enable just for html/css
autocmd FileType eruby,html,css EmmetInstall

" YCM

let g:ycm_server_use_vim_stdout = 0
let g:ycm_server_log_level = 'info'

"
" gutentags
"

"
" vim-angular: https://github.com/burnettk/vim-angular
"

let g:angular_find_ignore = ['lib/', 'dist/', 'managed-lib/', 'node_modules/']

"
" vim-javascript
"

let javascript_enable_domhtmlcss = 1

"
" vim-go (https://github.com/fatih/vim-go)
"

let g:go_auto_type_info = 1

" Run commands such as go run for the current file with <leader>r or go build
" and go test for the current package with <leader>b and <leader>t
" respectively. Display beautifully annotated source code to see which
" functions are covered with <leader>c.
au FileType go nmap <leader>r <Plug>(go-run)
au FileType go nmap <leader>b <Plug>(go-build)
au FileType go nmap <leader>t <Plug>(go-test)
au FileType go nmap <leader>c <Plug>(go-coverage)

" By default the mapping gd is enabled, which opens the target identifier in
" current buffer. You can also open the definition/declaration, in a new
" vertical, horizontal, or tab, for the word under your cursor:
au FileType go nmap <Leader>ds <Plug>(go-def-split)
au FileType go nmap <Leader>dv <Plug>(go-def-vertical)
au FileType go nmap <Leader>dt <Plug>(go-def-tab)

" Open the relevant Godoc for the word under the cursor with <leader>gd or
" open it vertically with <leader>gv
au FileType go nmap <Leader>gd <Plug>(go-doc)
au FileType go nmap <Leader>gv <Plug>(go-doc-vertical)

" open the Godoc in browser
au FileType go nmap <Leader>gb <Plug>(go-doc-browser)

" Show a list of interfaces which is implemented by the type under your cursor
" with <leader>s
au FileType go nmap <Leader>s <Plug>(go-implements)

" install go binaries here
let g:go_bin_path = expand("~/.gotools")

" Sometimes when using both vim-go and syntastic Vim will start lagging while
" saving and opening files. The following fixes this:
" let g:syntastic_go_checkers = ['golint', 'govet', 'errcheck']
" let g:syntastic_mode_map = { 'mode': 'active', 'passive_filetypes': ['go'] }
