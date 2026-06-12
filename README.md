#### AI-ChatBot System:

## Project Structure:

```text
.
├── backend
│   ├── alembic.ini
│   ├── app
│   │   ├── __init__.py
│   │   ├── api
│   │   │   ├── chat.py
│   │   │   ├── conversation.py
│   │   │   ├── file_generation.py
│   │   │   ├── file.py
│   │   │   ├── memory.py
│   │   │   ├── message.py
│   │   │   ├── user.py
│   │   │   └── ws.py
│   │   ├── core
│   │   │   ├── celery_app.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   ├── openapi.py
│   │   │   └── websocket.py
│   │   ├── crud
│   │   │   ├── conversation.py
│   │   │   ├── file.py
│   │   │   ├── memory.py
│   │   │   ├── message.py
│   │   │   ├── user_profile_snapshot.py
│   │   │   └── user.py
│   │   ├── db
│   │   │   ├── database.py
│   │   │   └── models
│   │   │       ├── __init__.py
│   │   │       ├── chunks.py
│   │   │       ├── conversation.py
│   │   │       ├── file.py
│   │   │       ├── memory.py
│   │   │       ├── message.py
│   │   │       ├── user_profile_snapshot.py
│   │   │       └── user.py
│   │   ├── enums
│   │   │   ├── __init__.py
│   │   │   └── memory.py
│   │   ├── prompts
│   │   │   ├── __init__.py
│   │   │   ├── chat.py
│   │   │   ├── context_router.py
│   │   │   ├── conversation_metadata.py
│   │   │   ├── file_generation.py
│   │   │   ├── intent_classification.py
│   │   │   ├── memory_comparison.py
│   │   │   ├── memory_extraction.py
│   │   │   ├── metadata_annotation.py
│   │   │   ├── profile_candidate.py
│   │   │   └── summarization.py
│   │   ├── schemas
│   │   │   ├── __init__.py
│   │   │   ├── conversation.py
│   │   │   ├── file_generation.py
│   │   │   ├── file.py
│   │   │   ├── import_convo.py
│   │   │   ├── llm.py
│   │   │   ├── memory.py
│   │   │   ├── message.py
│   │   │   ├── profile.py
│   │   │   └── user.py
│   │   ├── services
│   │   │   ├── conversation
│   │   │   │   ├── conversation_metadata_extractor.py
│   │   │   │   ├── conversation_metadata_service.py
│   │   │   │   ├── conversation_summary_memory_service.py
│   │   │   │   └── history_service.py
│   │   │   ├── embeddings
│   │   │   │   └── embedding_utils.py
│   │   │   ├── file_generation
│   │   │   │   ├── __init__.py
│   │   │   │   ├── file_generation_service.py
│   │   │   │   ├── file_renderer.py
│   │   │   │   └── intent_router.py
│   │   │   ├── file_processing
│   │   │   │   ├── file_chunkers.py
│   │   │   │   ├── file_processing_service.py
│   │   │   │   ├── file_processors.py
│   │   │   │   ├── file_task_dispatcher.py
│   │   │   │   └── file_type_config.py
│   │   │   ├── llm
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── llm_service.py
│   │   │   │   └── service.py
│   │   │   ├── memory
│   │   │   │   ├── background_memory_pipeline.py
│   │   │   │   ├── context_router.py
│   │   │   │   ├── lifecycle_service.py
│   │   │   │   ├── ltm_service.py
│   │   │   │   ├── memory_comparator.py
│   │   │   │   ├── memory_extractor.py
│   │   │   │   ├── memory_metadata_annotator.py
│   │   │   │   ├── memory_promoter.py
│   │   │   │   ├── memory_services.py
│   │   │   │   └── unified_memory_service.py
│   │   │   ├── message
│   │   │   │   └── message_service.py
│   │   │   ├── rag
│   │   │   │   └── retriever.py
│   │   │   ├── summarization
│   │   │   │   └── summarization_service.py
│   │   │   ├── time
│   │   │   │   └── timing.py
│   │   │   ├── tokenization
│   │   │   │   ├── token_service.py
│   │   │   │   └── tokenizer.py
│   │   │   └── user_profile
│   │   │       ├── profile_candidate_extractor.py
│   │   │       ├── profile_renderer.py
│   │   │       ├── profile_resolver.py
│   │   │       ├── user_profile_cache_service.py
│   │   │       └── user_profile_service.py
│   │   └── tasks
│   │       └── file_tasks.py
│   ├── main.py
│   ├── migrations
│   │   ├── env.py
│   │   ├── README
│   │   ├── script.py.mako
│   │   └── versions
│   │       ├── 08a95a832340_add_chunk_table.py
│   │       ├── 2f7fda260737_add_chunk_table.py
│   │       ├── 4f6e1c2b7d91_add_profile_items_to_user_profile_snapshot.py
│   │       ├── 6190823fd0cf_fixed_metadata_column_name.py
│   │       ├── 7427d97cd004_add_memory_vector_index.py
│   │       ├── 8172e3e4f9ce_add_memory_table.py
│   │       ├── 84b87b0473aa_merge_heads.py
│   │       ├── 8a51062bf617_added_role_field_to_message.py
│   │       ├── 971acdcdd25c_add_chunk_table.py
│   │       ├── be272f9da3f2_init.py
│   │       ├── c96bd23576a3_added_user_profile_snapshot.py
│   │       ├── e4ec87f109f1_add_vector_index.py
│   │       └── f1307cce4c40_fix_memory_table.py
│   ├── requirements.txt
│   ├── scripts
│   │   └── backfill_profile_metadata.py
│   └── tests
│       ├── test_context_router.py
│       └── test_file_generation_serializer.py
├── docker-compose.yaml
└── frontend
    ├── eslint.config.js
    ├── index.html
    ├── package-lock.json
    ├── package.json
    ├── public
    │   ├── favicon.svg
    │   └── icons.svg
    ├── README.md
    ├── src
    │   ├── App.jsx
    │   ├── components
    │   │   ├── ChatWindow.jsx
    │   │   ├── MessageInput.jsx
    │   │   ├── MessageList.jsx
    │   │   └── SideBar.jsx
    │   ├── hooks
    │   │   ├── useConversationSocket.js
    │   │   ├── useConversationUploads.js
    │   │   └── useFileGeneration.js
    │   ├── lib
    │   │   ├── api.js
    │   │   └── socket.js
    │   ├── main.jsx
    │   ├── pages
    │   │   └── ChatPage.jsx
    │   └── styles.css
    └── vite.config.js
```