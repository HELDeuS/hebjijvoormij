CREATE TABLE IF NOT EXISTS friends (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    password_hash VARCHAR(255),
    is_admin TINYINT(1) NOT NULL DEFAULT 0,
    is_super_admin TINYINT(1) NOT NULL DEFAULT 0,
    must_change_password TINYINT(1) NOT NULL DEFAULT 0,
    status ENUM('in_behandeling', 'actief', 'nonactief') NOT NULL DEFAULT 'actief',
    deactivation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tools (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    brand VARCHAR(100),
    model VARCHAR(100),
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_owner_tool (owner_id, name),
    FOREIGN KEY (owner_id) REFERENCES friends(id)
);

CREATE TABLE IF NOT EXISTS loans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_id INT NOT NULL,
    borrower_id INT NOT NULL,
    status ENUM('aangevraagd', 'uitgeleend', 'teruggekeerd', 'geweigerd') NOT NULL DEFAULT 'aangevraagd',
    note TEXT,
    date_from DATE,
    date_until DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lent_at DATE,
    returned_at DATE,
    active_flag TINYINT GENERATED ALWAYS AS (
        CASE WHEN status IN ('aangevraagd', 'uitgeleend') THEN 1 END
    ) VIRTUAL,
    UNIQUE KEY uq_active_loan (tool_id, active_flag),
    FOREIGN KEY (tool_id) REFERENCES tools(id),
    FOREIGN KEY (borrower_id) REFERENCES friends(id)
);

CREATE TABLE IF NOT EXISTS tool_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_id INT NOT NULL,
    linked_tool_id INT NOT NULL,
    UNIQUE KEY uq_link (tool_id, linked_tool_id),
    FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE,
    FOREIGN KEY (linked_tool_id) REFERENCES tools(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS circles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES friends(id)
);

CREATE TABLE IF NOT EXISTS circle_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    circle_id INT NOT NULL,
    friend_id INT NOT NULL,
    is_circle_admin TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE KEY uq_circle_member (circle_id, friend_id),
    FOREIGN KEY (circle_id) REFERENCES circles(id) ON DELETE CASCADE,
    FOREIGN KEY (friend_id) REFERENCES friends(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    friend_id INT NOT NULL,
    type VARCHAR(30) NOT NULL,
    message TEXT NOT NULL,
    link VARCHAR(255),
    ref_id INT,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (friend_id) REFERENCES friends(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    recipient_id INT NOT NULL,
    body TEXT NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES friends(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES friends(id) ON DELETE CASCADE
);
