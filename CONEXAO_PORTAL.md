# Conector do portal ao banco local

O conector recebe os pedidos do portal e grava no arquivo local `arena_alpha.db`.
Ele deve permanecer em execucao no computador onde esta o banco.

1. Defina a mesma chave `SYNC_SECRET` no Render e no computador.
2. Execute `Iniciar Conector do Portal.bat` e informe essa chave.
3. Abra outro terminal e execute `cloudflared tunnel --url http://127.0.0.1:5050`.
4. Copie o endereco `https://...trycloudflare.com` mostrado pelo Cloudflare.
5. No Render, defina `LOCAL_SYNC_URL` com esse endereco e `SYNC_SECRET` com a chave escolhida.

O endereco do tunnel muda sempre que ele for reiniciado. Quando isso acontecer,
atualize `LOCAL_SYNC_URL` no Render. Para um endereco fixo, crie um tunnel
nomeado na sua conta Cloudflare.
