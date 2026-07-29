-- ============================================================
-- Adaptive Bangla CAPTCHA (TicketMonarch) - MySQL Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS ticket_monarch
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ticket_monarch;

-- ------------------------------------------------------------
-- 1. Core Tables (migrated from SQLite)
-- ------------------------------------------------------------

CREATE TABLE users (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB;

CREATE TABLE captcha_sessions (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id       VARCHAR(64)  NOT NULL,
    user_id          INT UNSIGNED NULL,
    word_list        TEXT         NOT NULL COMMENT 'JSON: captcha_type, label/target_category, grid, etc.',
    difficulty       TINYINT UNSIGNED NOT NULL DEFAULT 2,
    solved           TINYINT(1)   NOT NULL DEFAULT 0,
    used             TINYINT(1)   NOT NULL DEFAULT 0,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_captcha_sessions_sid (session_id),
    KEY idx_captcha_sessions_user (user_id),
    CONSTRAINT fk_captcha_sessions_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE behavior_logs (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id        VARCHAR(64)  NOT NULL,
    user_ip           VARCHAR(64)  NULL,
    mouse_events      INT UNSIGNED NOT NULL DEFAULT 0,
    keyboard_events   INT UNSIGNED NOT NULL DEFAULT 0,
    bot_score         DOUBLE       NOT NULL DEFAULT 0,
    is_bot            TINYINT(1)   NOT NULL DEFAULT 0,
    confidence        DOUBLE       NOT NULL DEFAULT 0.5,
    method            VARCHAR(32)  NOT NULL DEFAULT 'unknown',
    label             VARCHAR(32)  NOT NULL DEFAULT 'unknown',
    features_json     TEXT         NULL COMMENT 'Extracted feature vector',
    events_json       TEXT         NULL COMMENT 'Raw event data',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_behavior_logs_session (session_id),
    KEY idx_behavior_logs_label (label),
    CONSTRAINT fk_behavior_logs_session
        FOREIGN KEY (session_id) REFERENCES captcha_sessions (session_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE bookings (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id           INT UNSIGNED NULL,
    session_id        VARCHAR(64)  NULL,
    destination       VARCHAR(128) NOT NULL,
    travel_date       VARCHAR(32)  NOT NULL,
    passengers        INT          NOT NULL DEFAULT 1,
    seat_preference   VARCHAR(64)  NULL,
    captcha_verified  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_bookings_user (user_id),
    KEY idx_bookings_session (session_id),
    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_bookings_session
        FOREIGN KEY (session_id) REFERENCES captcha_sessions (session_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE rl_episodes (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(64)  NULL,
    action          INT          NULL,
    action_name     VARCHAR(32)  NULL,
    difficulty      TINYINT UNSIGNED NULL,
    reward          DOUBLE       NOT NULL DEFAULT 0,
    is_bot          TINYINT(1)   NOT NULL DEFAULT 0,
    bot_score       DOUBLE       NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_rl_episodes_session (session_id),
    CONSTRAINT fk_rl_episodes_session
        FOREIGN KEY (session_id) REFERENCES captcha_sessions (session_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. Classifier / ML Tables
-- ------------------------------------------------------------

CREATE TABLE classifier_training_sessions (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    label           ENUM('human', 'bot') NOT NULL,
    source_file     VARCHAR(255) NULL,
    mouse_events    JSON NULL,
    keyboard_events JSON NULL,
    touch_events    JSON NULL,
    scroll_events   JSON NULL,
    feature_vector  JSON NULL COMMENT '118-dim extracted features',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cts_label (label),
    KEY idx_cts_created (created_at)
) ENGINE=InnoDB;

CREATE TABLE classifier_models (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    model_name        VARCHAR(128) NOT NULL,
    version           SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    model_path        VARCHAR(255) NOT NULL,
    pipeline_path     VARCHAR(255) NULL,
    scaler_path       VARCHAR(255) NULL,
    accuracy          DOUBLE NULL,
    precision_score   DOUBLE NULL,
    recall_score      DOUBLE NULL,
    f1_score          DOUBLE NULL,
    auc_roc           DOUBLE NULL,
    feature_names     JSON NULL,
    top_features      JSON NULL,
    hyperparameters   JSON NULL,
    training_samples  INT UNSIGNED NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_classifier_models_name_ver (model_name, version)
) ENGINE=InnoDB;

CREATE TABLE classifier_training_runs (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    model_id        INT UNSIGNED NULL,
    total_samples   INT UNSIGNED NULL,
    train_samples   INT UNSIGNED NULL,
    test_samples    INT UNSIGNED NULL,
    cv_folds        TINYINT UNSIGNED NULL,
    cv_scores       JSON NULL COMMENT 'Per-fold metrics',
    final_metrics   JSON NULL,
    hyperparameters JSON NULL,
    duration_sec    DOUBLE NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_ctr_model (model_id),
    CONSTRAINT fk_ctr_model
        FOREIGN KEY (model_id) REFERENCES classifier_models (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. RL Training Tables
-- ------------------------------------------------------------

CREATE TABLE rl_agent_checkpoints (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    agent_type      VARCHAR(32)  NOT NULL COMMENT 'ppo | softppo | dual_generator | simple_q',
    episode         INT UNSIGNED NULL,
    checkpoint_path VARCHAR(255) NOT NULL,
    is_best         TINYINT(1)   NOT NULL DEFAULT 0,
    avg_reward      DOUBLE       NULL,
    avg_accuracy    DOUBLE       NULL,
    metadata        JSON         NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_rlc_agent (agent_type),
    KEY idx_rlc_best (agent_type, is_best)
) ENGINE=InnoDB;

CREATE TABLE rl_training_runs (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    agent_type        VARCHAR(32)  NOT NULL,
    total_episodes    INT UNSIGNED NULL,
    total_steps       BIGINT UNSIGNED NULL,
    final_avg_reward  DOUBLE       NULL,
    final_avg_accuracy DOUBLE      NULL,
    difficulty_dist   JSON         NULL COMMENT '{1: n, 2: n, 3: n}',
    duration_sec      DOUBLE       NULL,
    config            JSON         NULL,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_rtr_agent (agent_type)
) ENGINE=InnoDB;

CREATE TABLE rl_q_table (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    state_key    VARCHAR(128) NOT NULL,
    action_1     DOUBLE NOT NULL DEFAULT 0,
    action_2     DOUBLE NOT NULL DEFAULT 0,
    action_3     DOUBLE NOT NULL DEFAULT 0,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_rl_qtable_state (state_key)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. Bangla Word Lexicon
-- ------------------------------------------------------------

CREATE TABLE captcha_word_lexicon (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    word        VARCHAR(64) NOT NULL,
    difficulty  TINYINT UNSIGNED NULL COMMENT 'Suggested difficulty tier',
    frequency   INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Times used',
    is_active   TINYINT(1) NOT NULL DEFAULT 1,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_captcha_word (word),
    KEY idx_captcha_word_diff (difficulty)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. System Configuration
-- ------------------------------------------------------------

CREATE TABLE system_config (
    config_key   VARCHAR(128) NOT NULL,
    config_value TEXT         NOT NULL,
    description  VARCHAR(512) NULL,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (config_key)
) ENGINE=InnoDB;

INSERT INTO system_config (config_key, config_value, description) VALUES
    ('bot_threshold',             '0.7',                        'Score >= this flags user as bot'),
    ('max_captcha_attempts',      '3',                          'Max wrong answers per session'),
    ('difficulty_levels',         '3',                          'Number of difficulty tiers'),
    ('easy_captcha_dataset',      'datasets/easy',              'Relative path to easy CAPTCHA image dataset'),
    ('medium_captcha_dataset',    'datasets/medium',            'Relative path to medium CAPTCHA category images'),
    ('medium_grid_size',          '3',                          'Grid dimensions for medium CAPTCHA'),
    ('medium_target_min',         '3',                          'Min target images in medium grid'),
    ('medium_target_max',         '5',                          'Max target images in medium grid'),
    ('jwt_expiry_hours',          '24',                         'JWT token lifetime in hours'),
    ('behavior_sample_interval',  '2000',                       'Frontend behavior sample interval ms'),
    ('rl_learning_rate',          '0.1',                        'SimpleRLAgent learning rate'),
    ('rl_gamma',                  '0.9',                        'SimpleRLAgent discount factor'),
    ('rl_epsilon',                '0.1',                        'SimpleRLAgent epsilon-greedy');

-- ------------------------------------------------------------
-- Useful Views
-- ------------------------------------------------------------

CREATE VIEW v_session_summary AS
SELECT
    cs.id,
    cs.session_id,
    u.username,
    cs.difficulty,
    cs.solved,
    cs.used,
    cs.created_at,
    (SELECT COUNT(*) FROM behavior_logs bl WHERE bl.session_id = cs.session_id) AS log_count,
    (SELECT bl2.bot_score
     FROM behavior_logs bl2
     WHERE bl2.session_id = cs.session_id
     ORDER BY bl2.id DESC LIMIT 1) AS latest_bot_score,
    (SELECT COUNT(*) FROM bookings b WHERE b.session_id = cs.session_id) AS booking_count
FROM captcha_sessions cs
LEFT JOIN users u ON u.id = cs.user_id;

CREATE VIEW v_bot_detection_stats AS
SELECT
    DATE(created_at)                        AS day,
    COUNT(*)                                AS total_logs,
    SUM(bot_score >= 0.7)                   AS detected_bots,
    SUM(bot_score < 0.7)                    AS detected_humans,
    ROUND(AVG(bot_score), 4)                AS avg_bot_score
FROM behavior_logs
WHERE bot_score IS NOT NULL
GROUP BY DATE(created_at);
