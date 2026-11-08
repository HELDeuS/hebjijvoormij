CREATE TABLE IF NOT EXISTS friends (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(50),
    password_hash VARCHAR(255),
    is_admin TINYINT(1) NOT NULL DEFAULT 0,
    must_change_password TINYINT(1) NOT NULL DEFAULT 0,
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

INSERT IGNORE INTO friends (name, email, phone, password_hash, is_admin, must_change_password)
VALUES ('admin', '', '',
        'scrypt:32768:8:1$ThfW3wfwfsCmUVdS$b1637a167f06b0d30093df10fbbc292d36d822a519c2c42568a01e381d2fc9a1a6d13651bbd82052b6120f06a66046c5eef79c4760b57d24b32c39e743f5068b',
        1, 1);
