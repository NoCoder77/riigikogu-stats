CREATE OR REPLACE VIEW v_votes_summary AS
SELECT
    v.id AS vote_id,
    v.title,
    v.vote_time,
    COUNT(*) FILTER (WHERE vc.choice = 'for') AS votes_for,
    COUNT(*) FILTER (WHERE vc.choice = 'against') AS votes_against,
    COUNT(*) FILTER (WHERE vc.choice = 'abstain') AS votes_abstain,
    COUNT(*) FILTER (WHERE vc.choice = 'did_not_vote') AS votes_did_not_vote,
    COUNT(*) FILTER (WHERE vc.choice = 'absent') AS votes_absent,
    COUNT(*) AS total_casts
FROM votes v
LEFT JOIN vote_casts vc ON vc.vote_id = v.id
GROUP BY v.id, v.title, v.vote_time;

CREATE OR REPLACE VIEW v_person_attendance_rate AS
SELECT
    p.id AS person_id,
    p.full_name,
    COUNT(sa.session_id) AS sessions_recorded,
    COUNT(*) FILTER (WHERE sa.status IN ('present', 'kohal', 'presented')) AS present_count,
    COUNT(*) FILTER (WHERE sa.status IN ('absent', 'puudus')) AS absent_count
FROM persons p
LEFT JOIN session_attendance sa ON sa.person_id = p.id
GROUP BY p.id, p.full_name;

CREATE OR REPLACE VIEW v_vote_participation AS
SELECT
    p.id AS person_id,
    p.full_name,
    COUNT(vc.vote_id) AS votes_recorded,
    COUNT(*) FILTER (WHERE vc.choice = 'for') AS votes_for,
    COUNT(*) FILTER (WHERE vc.choice = 'against') AS votes_against,
    COUNT(*) FILTER (WHERE vc.choice = 'abstain') AS votes_abstain,
    COUNT(*) FILTER (WHERE vc.choice = 'did_not_vote') AS votes_did_not_vote,
    COUNT(*) FILTER (WHERE vc.choice = 'absent') AS votes_absent
FROM persons p
LEFT JOIN vote_casts vc ON vc.person_id = p.id
GROUP BY p.id, p.full_name;

CREATE OR REPLACE VIEW v_faction_vote_counts AS
SELECT
    pf.faction_id,
    f.name AS faction_name,
    vc.choice,
    COUNT(*) AS vote_count
FROM person_faction_membership pf
JOIN factions f ON f.id = pf.faction_id
JOIN vote_casts vc ON vc.person_id = pf.person_id
GROUP BY pf.faction_id, f.name, vc.choice;
