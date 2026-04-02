Pacote pronto para Render com Postgres + modo híbrido.

1. Suba os arquivos no GitHub.
2. Crie um Web Service no Render.
3. Configure a env var DATABASE_URL com a connection string do seu Render Postgres.
4. Depois abra /api/health e confira se storage ficou como postgres.

Se DATABASE_URL não estiver configurado, o sistema cai para data_store.json local apenas como fallback.
