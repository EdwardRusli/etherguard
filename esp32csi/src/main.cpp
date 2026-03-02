/**
 * EtherGuard — ESP32 CSI Fall Detector v3.1
 *
 * Collects WiFi Channel State Information and streams it over USB serial
 * at 115200 baud in ESP32 CSI Toolkit CSV text format.
 *
 * CSI Triggering Strategy:
 *   The ESP32 sends UDP packets to the ROUTER (WiFi gateway) at a fixed
 *   interval (default 20 ms = 50 Hz). Each transmitted frame causes the
 *   router to send a WiFi ACK, which the ESP32 receives — triggering the
 *   CSI RX callback. This gives us a predictable CSI sampling rate.
 *
 *   NOTE: Sending to our OWN IP does NOT work — no RX WiFi frame is
 *   generated because the packet never leaves the ESP32's network stack.
 *
 * Output format:
 *   CSI_DATA,<seq>,<mac>,<rssi>,<rate>,<sig_mode>,<mcs>,<bw>,<sm>,<ns>,
 *   <agg>,<stbc>,<fec>,<sgi>,<noise>,<ampdu>,<ch>,<sch>,<ts>,
 *   <ant>,<sig_len>,<rx_state>,<len>,<fw>,"[i0,r0,i1,r1,...]"
 *
 * Hardware: ESP32 (NodeMCU, TTGO T8, etc.)
 * Baud:     115200
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_wifi.h>
#include <esp_timer.h>

// ─────────────────────────────────────────────
//  CONFIGURATION
// ─────────────────────────────────────────────
static const char* WIFI_SSID     = "eternacupnoodle";
static const char* WIFI_PASSWORD = "semogasuksesamin";

// Ping interval in milliseconds → target CSI rate
// 20 ms  = 50 Hz
static const uint32_t PING_INTERVAL_MS  = 20;

// UDP port for pings to the router
static const uint16_t PING_PORT  = 12399;

// ─────────────────────────────────────────────
//  GLOBALS
// ─────────────────────────────────────────────
static WiFiUDP     udp;
static IPAddress   gateway_ip;
static uint32_t    seq          = 0;
static volatile uint32_t csi_count = 0;
static uint32_t    ping_count   = 0;
static uint32_t    drop_count   = 0;

// Simple lock: CSI callback sets this flag while printing
static volatile bool csi_printing = false;

// ─────────────────────────────────────────────
//  CSI CALLBACK — called from WiFi task context
// ─────────────────────────────────────────────
static void wifi_csi_cb(void* ctx, wifi_csi_info_t* info) {
    if (!info || !info->buf || info->len == 0) return;

    csi_count++;

    // Skip if we're still printing a previous frame
    if (csi_printing) {
        drop_count++;
        return;
    }
    csi_printing = true;

    const int8_t* buf = info->buf;
    const int     len = info->len;

    // MAC address
    char mac_str[18];
    snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
             info->mac[0], info->mac[1], info->mac[2],
             info->mac[3], info->mac[4], info->mac[5]);

    // Build the full CSV line into a buffer to minimize Serial calls
    // Max line size: ~80 header + 128*5 data ≈ 720 bytes, use 1024 to be safe
    static char line[1400];
    int pos = 0;

    // Header fields
    pos += snprintf(line + pos, sizeof(line) - pos,
        "CSI_DATA,%u,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%u,%d,%d,%d,%d,%d,\"[",
        seq++,
        mac_str,
        info->rx_ctrl.rssi,
        info->rx_ctrl.rate,
        info->rx_ctrl.sig_mode,
        info->rx_ctrl.mcs,
        info->rx_ctrl.cwb,
        info->rx_ctrl.smoothing,
        info->rx_ctrl.not_sounding,
        info->rx_ctrl.aggregation,
        info->rx_ctrl.stbc,
        info->rx_ctrl.fec_coding,
        info->rx_ctrl.sgi,
        info->rx_ctrl.noise_floor,
        info->rx_ctrl.ampdu_cnt,
        info->rx_ctrl.channel,
        info->rx_ctrl.secondary_channel,
        (uint32_t)esp_timer_get_time(),
        info->rx_ctrl.ant,
        info->rx_ctrl.sig_len,
        info->rx_ctrl.rx_state,
        len,
        0  // first_word placeholder
    );

    // CSI data values: [imag0,real0,imag1,real1,...]
    for (int i = 0; i < len && pos < (int)sizeof(line) - 10; i++) {
        if (i > 0) line[pos++] = ',';
        pos += snprintf(line + pos, sizeof(line) - pos, "%d", (int)buf[i]);
    }

    // Close the array and line
    pos += snprintf(line + pos, sizeof(line) - pos, "]\"\n");

    // Single Serial.write call — much faster than multiple Serial.print
    Serial.write((const uint8_t*)line, pos);

    csi_printing = false;
}

// ─────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println();
    Serial.println("========================================");
    Serial.println("  EtherGuard ESP32 CSI Collector v3.1  ");
    Serial.println("  Baud: 115200 | Format: CSV text       ");
    Serial.println("========================================");

    // ── Connect to WiFi ──
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("Connecting to ");
    Serial.print(WIFI_SSID);

    int tries = 0;
    while (WiFi.status() != WL_CONNECTED && tries < 40) {
        delay(500);
        Serial.print(".");
        tries++;
    }
    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[ERROR] WiFi failed! Restarting...");
        delay(3000);
        ESP.restart();
    }

    gateway_ip = WiFi.gatewayIP();

    Serial.print("[WiFi] IP:      ");  Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Gateway: ");  Serial.println(gateway_ip);
    Serial.print("[WiFi] Channel: ");  Serial.println(WiFi.channel());
    Serial.print("[WiFi] RSSI:    ");  Serial.println(WiFi.RSSI());

    // ── Start UDP ──
    udp.begin(PING_PORT);

    // ── Enable CSI collection ──
    wifi_csi_config_t csi_cfg = {};
    csi_cfg.lltf_en           = true;
    csi_cfg.htltf_en          = true;
    csi_cfg.stbc_htltf2_en    = true;
    csi_cfg.ltf_merge_en      = true;
    csi_cfg.channel_filter_en = false;
    csi_cfg.manu_scale        = false;
    csi_cfg.shift             = 0;

    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_cfg));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_cb, NULL));

    Serial.println("[CSI] Collection enabled");
    Serial.print("[Ping] Target: ");
    Serial.print(gateway_ip);
    Serial.print(":");
    Serial.print(PING_PORT);
    Serial.print(" @ ");
    Serial.print(1000 / PING_INTERVAL_MS);
    Serial.println(" Hz");

    Serial.println();
    Serial.println("--- CSI stream starting ---");
    Serial.println();
}

// ─────────────────────────────────────────────
//  LOOP — sends pings & heartbeats
// ─────────────────────────────────────────────
void loop() {
    static uint32_t last_ping      = 0;
    static uint32_t last_heartbeat = 0;
    static uint32_t prev_csi_count = 0;

    uint32_t now = millis();

    // ── Send UDP ping to the router at fixed intervals ──
    if (now - last_ping >= PING_INTERVAL_MS) {
        last_ping = now;
        udp.beginPacket(gateway_ip, PING_PORT);
        udp.write((const uint8_t*)"P", 1);
        udp.endPacket();
        ping_count++;
    }

    // ── Drain any incoming UDP ──
    while (udp.parsePacket() > 0) {
        udp.flush();
    }

    // ── Heartbeat every 5 seconds ──
    if (now - last_heartbeat >= 5000) {
        uint32_t cur_csi = csi_count;
        uint32_t delta   = cur_csi - prev_csi_count;
        float    rate    = (float)delta / 5.0f;

        // Only print heartbeat when CSI callback is not printing
        if (!csi_printing) {
            Serial.println();
            Serial.print("[HB] CSI_total=");
            Serial.print(cur_csi);
            Serial.print(" CSI_rate=");
            Serial.print(rate, 1);
            Serial.print(" Hz | pings=");
            Serial.print(ping_count);
            Serial.print(" | drops=");
            Serial.print(drop_count);
            Serial.print(" | RSSI=");
            Serial.print(WiFi.RSSI());
            Serial.print(" dBm | gw=");
            Serial.println(gateway_ip);
        }

        prev_csi_count = cur_csi;
        last_heartbeat = now;
    }

    delay(1);
}
