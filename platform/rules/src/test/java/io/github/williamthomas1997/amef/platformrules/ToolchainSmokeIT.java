package io.github.williamthomas1997.amef.platformrules;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * Proves that the build environment can run Testcontainers-based integration tests (Docker reachable, image
 * pulls work, mapped ports reachable). Later milestones rely on this for Redis, Kafka and Postgres ITs.
 * Deliberately not {@code disabledWithoutDocker}: without Docker this test must fail, not skip.
 */
@Testcontainers
class ToolchainSmokeIT {

    static final String REDIS_IMAGE = "redis:7.4-alpine";

    @Container
    static final GenericContainer<?> REDIS = new GenericContainer<>(REDIS_IMAGE).withExposedPorts(6379);

    @Test
    void containerStartsAndAnswers() throws IOException {
        try (Socket socket = new Socket(REDIS.getHost(), REDIS.getMappedPort(6379))) {
            socket.setSoTimeout(5_000);
            OutputStream out = socket.getOutputStream();
            out.write("PING\r\n".getBytes(StandardCharsets.US_ASCII));
            out.flush();
            var in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.US_ASCII));

            assertThat(in.readLine()).isEqualTo("+PONG");
        }
    }
}
