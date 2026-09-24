DROP VIEW IF EXISTS v_votes_summary;
CREATE VIEW v_votes_summary AS
SELECT
    v.id AS vote_id,
    v.title,
    v.vote_time,
    SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
    SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
    SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
    SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
    SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent,
    COUNT(*) AS total_casts
FROM votes v
LEFT JOIN vote_casts vc ON vc.vote_id = v.id
GROUP BY v.id, v.title, v.vote_time;

DROP VIEW IF EXISTS v_person_attendance_rate;
CREATE VIEW v_person_attendance_rate AS
SELECT
    p.id AS person_id,
    p.full_name,
    COUNT(sa.session_id) AS sessions_recorded,
    SUM(CASE WHEN sa.status IN ('present', 'kohal', 'presented') THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN sa.status IN ('absent', 'puudus') THEN 1 ELSE 0 END) AS absent_count
FROM persons p
LEFT JOIN session_attendance sa ON sa.person_id = p.id
GROUP BY p.id, p.full_name;

DROP VIEW IF EXISTS v_vote_participation;
CREATE VIEW v_vote_participation AS
SELECT
    p.id AS person_id,
    p.full_name,
    COUNT(vc.vote_id) AS votes_recorded,
    SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
    SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
    SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
    SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
    SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
FROM persons p
LEFT JOIN vote_casts vc ON vc.person_id = p.id
GROUP BY p.id, p.full_name;

DROP VIEW IF EXISTS v_faction_vote_counts;
CREATE VIEW v_faction_vote_counts AS
SELECT
    pf.faction_id,
    f.name AS faction_name,
    vc.choice,
    COUNT(*) AS vote_count
FROM vote_casts vc
JOIN votes v ON v.id = vc.vote_id
JOIN person_faction_membership pf ON pf.person_id = vc.person_id
    AND date(v.vote_time) >= date(pf.start_date)
    AND (pf.end_date IS NULL OR date(v.vote_time) <= date(pf.end_date))
JOIN factions f ON f.id = pf.faction_id
GROUP BY pf.faction_id, f.name, vc.choice;

DROP VIEW IF EXISTS v_faction_attendance;
CREATE VIEW v_faction_attendance AS
SELECT
    pf.faction_id,
    COUNT(*) AS total_slots,
    SUM(CASE WHEN sa.status IN ('present', 'kohal', 'presented') THEN 1 ELSE 0 END) AS present_slots,
    SUM(CASE WHEN sa.status IN ('absent', 'puudus') THEN 1 ELSE 0 END) AS absent_slots
FROM sessions s
JOIN person_faction_membership pf ON date(s.session_date) >= date(pf.start_date)
    AND (pf.end_date IS NULL OR date(s.session_date) <= date(pf.end_date))
LEFT JOIN session_attendance sa ON sa.session_id = s.id AND sa.person_id = pf.person_id
GROUP BY pf.faction_id;
