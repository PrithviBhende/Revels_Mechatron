#include <WiFi.h>
#include <ESPmDNS.h>

const char* ssid = "TP-LINK_5C4A";
const char* password = "86124560";

WiFiServer server(8080);
String macStr;

void setup() {
  Serial.begin(115200);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");

  // Get & print MAC
  macStr = WiFi.macAddress();
  macStr.replace(":", "");

  Serial.println("ESP32 MAC Address:");
  Serial.println(macStr);

  // Create hostname using MAC
  String hostname = "esp-" + macStr;

  if (MDNS.begin(hostname.c_str())) {
    Serial.println("mDNS started");
    Serial.println(hostname + ".local");
  } else {
    Serial.println("mDNS failed");
  }

  server.begin();
  Serial.println("TCP Server started on port 8080");
}

void loop() {
  WiFiClient client = server.available();
  if (!client) return;

  Serial.println("Client connected");

  while (client.connected()) {
    if (client.available()) {
      String cmd = client.readStringUntil('\n');
      cmd.trim();

      Serial.print("Received: ");
      Serial.println(cmd);

      // You will parse commands here later
      // Example: T1_ON, T2_OFF
    }
  }

  client.stop();
  Serial.println("Client disconnected");
}
