-- Создание таблицы
CREATE TABLE news (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  content TEXT,
  source_channel TEXT NOT NULL,
  pub_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  language TEXT,
  processed BOOLEAN DEFAULT FALSE,
  keywords TEXT[],
  is_duplicate BOOLEAN DEFAULT FALSE,
  original_message_id BIGINT
);

-- Индексы
CREATE INDEX idx_news_title ON news(title);
CREATE INDEX idx_news_pub_date ON news(pub_date DESC);
CREATE INDEX idx_news_channel ON news(source_channel);
