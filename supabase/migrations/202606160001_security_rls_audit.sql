ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_owner_access ON profiles;
CREATE POLICY profiles_owner_access ON profiles
  FOR ALL USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

DROP POLICY IF EXISTS workspaces_owner_access ON workspaces;
CREATE POLICY workspaces_owner_access ON workspaces
  FOR ALL USING (owner_id = auth.uid()::text)
  WITH CHECK (owner_id = auth.uid()::text);

DROP POLICY IF EXISTS agents_workspace_owner_access ON agents;
CREATE POLICY agents_workspace_owner_access ON agents
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = agents.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = agents.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS agent_modules_workspace_owner_access ON agent_modules;
CREATE POLICY agent_modules_workspace_owner_access ON agent_modules
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM agents
      JOIN workspaces ON workspaces.id = agents.workspace_id
      WHERE agents.id = agent_modules.agent_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM agents
      JOIN workspaces ON workspaces.id = agents.workspace_id
      WHERE agents.id = agent_modules.agent_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS projects_workspace_owner_access ON projects;
CREATE POLICY projects_workspace_owner_access ON projects
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = projects.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = projects.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS files_workspace_owner_access ON files;
CREATE POLICY files_workspace_owner_access ON files
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = files.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = files.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS conversations_workspace_owner_access ON conversations;
CREATE POLICY conversations_workspace_owner_access ON conversations
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = conversations.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = conversations.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS messages_workspace_owner_access ON messages;
CREATE POLICY messages_workspace_owner_access ON messages
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM conversations
      JOIN workspaces ON workspaces.id = conversations.workspace_id
      WHERE conversations.id = messages.conversation_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations
      JOIN workspaces ON workspaces.id = conversations.workspace_id
      WHERE conversations.id = messages.conversation_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS memories_workspace_owner_access ON memories;
CREATE POLICY memories_workspace_owner_access ON memories
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = memories.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM workspaces
      WHERE workspaces.id = memories.workspace_id
      AND workspaces.owner_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS audit_logs_owner_access ON audit_logs;
CREATE POLICY audit_logs_owner_access ON audit_logs
  FOR SELECT USING (user_id = auth.uid()::text);
