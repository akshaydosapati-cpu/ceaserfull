BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260606_0001

CREATE TABLE users (
    email VARCHAR(255) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE profiles (
    user_id VARCHAR(36) NOT NULL, 
    display_name VARCHAR(255), 
    avatar_url VARCHAR(1000), 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id)
);

CREATE TABLE workspaces (
    owner_id VARCHAR(36) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    type VARCHAR(50) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_workspaces_owner_id ON workspaces (owner_id);

CREATE TABLE agents (
    workspace_id VARCHAR(36) NOT NULL, 
    name VARCHAR(80) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_agents_workspace_id ON agents (workspace_id);

CREATE TABLE projects (
    workspace_id VARCHAR(36) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description VARCHAR(2000), 
    status VARCHAR(50) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_projects_workspace_id ON projects (workspace_id);

CREATE TABLE conversations (
    workspace_id VARCHAR(36) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_conversations_workspace_id ON conversations (workspace_id);

CREATE TABLE memories (
    workspace_id VARCHAR(36) NOT NULL, 
    memory_type VARCHAR(80) NOT NULL, 
    content VARCHAR NOT NULL, 
    metadata JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_memories_workspace_id ON memories (workspace_id);

CREATE TABLE agent_modules (
    agent_id VARCHAR(36) NOT NULL, 
    module_name VARCHAR(120) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(agent_id) REFERENCES agents (id) ON DELETE CASCADE
);

CREATE INDEX ix_agent_modules_agent_id ON agent_modules (agent_id);

CREATE TABLE files (
    workspace_id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36), 
    name VARCHAR(255) NOT NULL, 
    file_type VARCHAR(80) NOT NULL, 
    storage_path VARCHAR(1000) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_files_workspace_id ON files (workspace_id);

CREATE INDEX ix_files_project_id ON files (project_id);

CREATE TABLE messages (
    conversation_id VARCHAR(36) NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    content VARCHAR NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

INSERT INTO alembic_version (version_num) VALUES ('20260606_0001') RETURNING alembic_version.version_num;

COMMIT;

