CREATE TYPE status_enum
AS
ENUM('active', 'inactive');

CREATE TYPE type_enum
AS
ENUM('paid_monthly', 'friend_lifetime', 'giveaway_lifetime', 'paid_lifetime','giveaway_monthly');


CREATE TABLE subscribers (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	chat_id BIGINT UNIQUE NOT NULL,
	tg_username VARCHAR(33) UNIQUE,
	status STATUS_ENUM NOT NULL,
	joined_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
	expire_at TIMESTAMPTZ,
	is_permanent BOOLEAN NOT NULL	
);




CREATE TABLE access_codes (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	code TEXT UNIQUE NOT NULL,
	code_type TYPE_ENUM NOT NULL,
	is_used BOOLEAN DEFAULT FALSE NOT NULL,
	redeemed_chat_id BIGINT,
	
	CONSTRAINT redeem_chat_id 
    FOREIGN KEY (redeemed_chat_id) 
    REFERENCES subscribers(chat_id) 
    ON DELETE CASCADE
	
);


CREATE TABLE alert_history (
	fissure_id TEXT PRIMARY KEY,
	mission_type TEXT DEFAULT 'Void Cascade',
	fissure_tier TEXT DEFAULT 'Omnia',
	node TEXT DEFAULT 'Tuvul Commons',
	enemy_faction TEXT,
	is_steel_path BOOLEAN NOT NULL,
	is_void_storm BOOLEAN DEFAULT FALSE,
	activation_time TIMESTAMPTZ NOT NULL,
	expiry_time TIMESTAMPTZ NOT NULL,
	created_at TIMESTAMPTZ DEFAULT NOW()	
	
);