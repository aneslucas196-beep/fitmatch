-- Ajoute la colonne working_hours pour les horaires personnalisés des coachs
ALTER TABLE users ADD COLUMN IF NOT EXISTS working_hours TEXT;
