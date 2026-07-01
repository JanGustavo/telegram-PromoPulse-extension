# Changelog

## [1.5.2] - 2026-07-01

### 🔔 Notificações Enriquecidas do Chrome (Fase 3)
- **Integração com `chrome.notifications`:** Substituição da API de notificações padrão do navegador pelo recurso avançado de Notificações Ricas do Chrome.
- **Preview de Imagens de Produtos:** A notificação agora exibe dinamicamente a foto real do produto e o preço extraído em alta qualidade quando capturado pelo Radar.
- **Ações Rápidas na Notificação:** Adicionado o botão "Ir para a Oferta ➔" diretamente na notificação nativa do sistema. Ao clicar, o navegador abre a oferta automaticamente em uma nova aba do Chrome.

## [1.5.1] - 2026-07-01

### 🎯 Personalização Avançada de Alertas (Fase 3)
- **Filtros por Marcas e Modelos:** Implementada a lógica completa de correspondência para os níveis de correspondência `"mid"` (marca + categoria) e `"specific"` (modelos específicos).
- **Limites de Preço por Modelo:** O radar agora permite definir limites de preço específicos para cada modelo digitado (ex: `iPhone 15 Pro Max : 5500`), sobrescrevendo o limite de preço global quando o produto específico for detectado.
- **Correção de UI:** Agora os campos de texto do painel da extensão são recarregados corretamente a partir das configurações salvas.

## [1.5.0] - 2026-07-01

### 💾 Persistência com SQLite & Recuperação de Falhas (Fase 2)
- **Persistência Completa de Estado:** Implementação de banco de dados SQLite local (`promopulse.db`) para guardar o histórico de alertas, configurações do radar e status ativo de monitoramento.
- **Recuperação de Inicialização:** Se o servidor reiniciar por qualquer motivo, ele agora restaura automaticamente o monitoramento se estivesse ativo anteriormente.
- **Mídia no Dashboard:** Download automático de mídias de ofertas e de imagens de visualização de links da web do Telegram diretamente na pasta persistida, exibindo fotos dos produtos no painel.
- **Botão Direto de Oferta:** Adicionado botão de ação rápida "Ir para a Oferta" no rodapé de cada alerta.
- **Resiliência do Telethon:** Nova rotina assíncrona com loop de reconexão e tentativas infinitas em caso de instabilidades.
- **Testes Unitários:** Adicionado conjunto de testes automatizados (`test_server.py`) cobrindo as funções e regras de negócio de extração e filtros.

### 🔗 Enriquecimento e Parsing de Links (Fase 3)
- **Extração de Links:** Enriquecimento em background de alertas através do download de metadados, títulos originais limpos de clickbaits, preços reais e fotos de links de e-commerce (Amazon, Magalu, Shopee e Mercado Livre).

## [1.4.0] - 2026-06-29

### 🔍 Filtros de Busca e Tema Claro/Escuro (Fase 1)
- **Filtros e Sniper Mode na Extensão:** Adicionado suporte para filtros rápidos de busca por palavras-chave e faixa de preço mínimo/máximo na aba de alertas.
- **Dark Mode:** Botão para alternância dinâmica entre tema claro e escuro no dashboard.
- **Swagger/OpenAPI:** Documentação enriquecida de schemas OpenAPI com tipagem robusta no FastAPI.

## [1.3.0] - 2026-04-24

### ✨ Resiliência e Persistência de Estado (F5)

- **Mantimento de Funcionamento:** O radar agora sincroniza seu estado com o backend ao recarregar a página (F5). Se o monitoramento estiver ativo no servidor, a interface restaurará automaticamente o botão "Monitorando" e o polling de alertas.

- **Persistência de Alertas:** Implementação de persistência local do `lastAlertId`. Ao atualizar o dashboard, o sistema não dispara notificações duplicadas para ofertas que o usuário já visualizou antes do refresh.

- **Sincronização de Configurações:** Sincronização automática da lista de grupos monitorados entre o frontend e o backend durante a inicialização da sessão.

## [1.1.0] - 2026-04-20

### ✨ Novidades e Inteligência

- Sistema de Abas Independentes: Os níveis de monitoramento (Amplo, Marcas e Modelos) agora funcionam como menus isolados, permitindo ativar ou pausar cada radar de forma individual sem interferência entre os painéis.

- "Clickbait Killer": Implementação de lógica para extrair o nome real do produto, removendo frases de gatilho comuns em canais de ofertas (ex: "NGM MERECE COMER MARMITA FRIA").

- Expansão de Categorias: Adição de suporte completo para monitoramento de Moda & Acessórios, Games & Hardware e Esportes.

- Detecção de Pagamento: O motor agora identifica condições de preço, como descontos exclusivos no PIX ou parcelamentos sem juros.

### 🛠️ Arquitetura e Performance

- Modularização de Estilos: Migração de todo o CSS interno da extensão para um arquivo dedicado (dashboard.css), facilitando a manutenção e o carregamento.

- Refatoração do Backend: Reorganização estrutural do server.py para suportar múltiplos níveis de busca simultâneos e processamento paralelo de categorias.

- Automação de Releases: Integração total com GitHub Actions para geração automática de pacotes .zip e publicação de releases a cada nova tag de versão.

### 🐞 Correções

- Isolamento de Memória: Correção de bug onde a seleção de uma categoria em um nível ativava erroneamente a mesma categoria em outro painel.

- Sanitização de Cache: Implementação de rotina para limpar estados antigos de memória (Ghost State) ao carregar novas versões da extensão.
