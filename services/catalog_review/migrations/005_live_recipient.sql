-- No recipients are seeded. Application environment policy still restricts
-- tests/staging to synthetic accounts; production requires launch evidence.
ALTER TABLE invitations DROP CONSTRAINT invitations_recipient_check;
ALTER TABLE invitations ADD CONSTRAINT invitations_recipient_check
    CHECK (length(recipient) <= 254 AND recipient ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$');
