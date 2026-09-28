# Build the shared reviewer image first; this verifier calls no AI model.
FROM chb-reviewer:machine-v1
COPY test.sh verify.cjs /tests/
RUN chmod +x /tests/test.sh
