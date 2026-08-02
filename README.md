# Arena Alpha

Sistema de gestão esportiva com uma aplicação web pública conectada ao mesmo banco de dados (`arena_alpha.db`).

## Portal e links públicos

Depois de publicar a aplicação, divulgue os seguintes endereços no seu domínio:

- `/aulas` — agendamento de aula experimental;
- `/eventos` — solicitação de reserva para evento;
- `/portal` — portal do aluno com plano e histórico de pagamentos.

O aluno entra no portal usando o CPF e a data de nascimento já cadastrados no sistema. Para o portal funcionar, preencha esses dois campos ao cadastrar cada aluno.

As solicitações de aulas vão para `aulas_experimentais`; as reservas de evento entram na `agenda`; e o portal consulta a tabela `pagamentos`. Tudo usa o mesmo arquivo de banco do sistema.

## Como executar localmente

No PowerShell, dentro desta pasta:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abra `http://localhost:5000` no navegador.

## Publicação no Render pelo GitHub

O projeto está pronto para criar um serviço web no Render. O arquivo `render.yaml` instala as dependências, inicia o Flask, cria uma `SECRET_KEY` aleatória e grava o banco SQLite em disco persistente.

1. Crie um repositório privado no GitHub e envie esta pasta (o `.gitignore` impede o envio do banco local);
2. Entre em [dashboard.render.com](https://dashboard.render.com), escolha **New > Blueprint** e conecte o repositório;
3. Confirme o plano **Starter**: o disco persistente necessário para preservar agenda, cadastros e pagamentos requer serviço pago;
4. Após o deploy, o Render mostra o endereço público, no formato `https://arena-alpha-portal.onrender.com`.

O serviço é atualizado automaticamente a cada novo envio para o GitHub. Antes da primeira publicação, faça um backup do arquivo local `arena_alpha.db`; para levar os cadastros atuais para a internet, ele deve ser enviado uma única vez ao disco persistente do serviço.
