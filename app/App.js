import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useEffect, useState } from "react";
import {
  View,
  Text,
  ActivityIndicator,
  Button,
  Image,
  ScrollView,
  StyleSheet,
} from "react-native";
import { API } from "./lib/api";
import { CameraView, useCameraPermissions } from "expo-camera";

// --- Home Screen ---
function HomeScreen() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await API.get("/api/ping");
        setStatus(r.data?.ok ? "✅ Connected" : "⚠️ Ping failed");
      } catch (e) {
        setStatus("❌ " + (e?.message || "Error"));
      }
    })();
  }, []);

  return (
    <View style={styles.center}>
      {!status ? <ActivityIndicator /> : <Text style={{ fontSize: 18 }}>{status}</Text>}
    </View>
  );
}

// --- Scan Screen ---
function ScanScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [product, setProduct] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!permission) requestPermission();
  }, [permission]);

  if (!permission) return <Center><Text>Checking camera permission…</Text></Center>;
  if (!permission.granted) {
    return (
      <Center>
        <Text style={{ marginBottom: 8 }}>Camera permission is required</Text>
        <Button title="Grant permission" onPress={requestPermission} />
      </Center>
    );
  }

  const onBarcodeScanned = async ({ data }) => {
    console.log("Scanned barcode:", data);

    if (scanned) return;
    setScanned(true);
    setLoading(true);
    setError(null);
    setProduct(null);

    try {
      const res = await API.get(`/api/products/${encodeURIComponent(data)}/`);
      console.log("API response keys:", Object.keys(res.data));
      setProduct(res.data);
    } catch (e) {
      console.log("API error:", e.message);
      setError("Not found or network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1 }}>
      {!scanned && (
        <CameraView
          style={{ flex: 1 }}
          facing="back"
          barcodeScannerSettings={{
            barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128", "qr"],
          }}
          onBarcodeScanned={onBarcodeScanned}
        />
      )}

      {scanned && (
        <View style={{ flex: 1 }}>
          {loading && <Center><ActivityIndicator /></Center>}
          {error && <Center><Text>❌ {error}</Text></Center>}
          {!loading && product && (
            <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
              <ProductCard product={product} />
            </ScrollView>
          )}
          {!loading && !product && !error && (
            <Center><Text>No product data</Text></Center>
          )}

          <View style={{ padding: 12 }}>
            <Button
              title="Scan again"
              onPress={() => {
                setScanned(false);
                setProduct(null);
                setError(null);
              }}
            />
          </View>
        </View>
      )}
    </View>
  );
}

// --- Product Card (expanded) ---
function ProductCard({ product }) {
  console.log("ProductCard props:", product); // debug log

  if (!product) return <View style={styles.card}><Text>No product data</Text></View>;

  return (
    <View style={styles.card}>
      {/* Debug keys (helps verify what fields arrived) */}
      <Text style={styles.debug}>
        Debug keys: {Object.keys(product).join(", ")}
      </Text>

      {product.image && (
        <Image source={{ uri: product.image }} style={styles.image} />
      )}

      <Text style={styles.name}>{product.name}</Text>
      <Text style={styles.brand}>{product.brand || "—"}</Text>
      {"score" in product && (
        <Text style={styles.score}>Health Score: {product.score}/100</Text>
      )}

      {/* Ingredients */}
      {product.ingredients_text ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Ingredients</Text>
          <Text style={styles.text}>{product.ingredients_text}</Text>
        </View>
      ) : null}

      {/* Nutrition facts */}
      {product.nutrition && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Nutrition (per 100g)</Text>
          {Object.entries(product.nutrition).map(([k, v]) =>
            v != null ? (
              <Text key={k} style={styles.text}>
                • {niceKey(k)}: {v}{k.includes("mg") ? " mg" : " g"}
              </Text>
            ) : null
          )}
        </View>
      )}

      {/* Positives */}
      {Array.isArray(product.positives) && product.positives.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "green" }]}>✅ Positives</Text>
          {product.positives.map((p, i) => (
            <Text key={i} style={styles.text}>• {p}</Text>
          ))}
        </View>
      )}

      {/* Negatives */}
      {Array.isArray(product.negatives) && product.negatives.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "red" }]}>⚠️ Negatives</Text>
          {product.negatives.map((n, i) => (
            <Text key={i} style={styles.text}>• {n}</Text>
          ))}
        </View>
      )}

      {/* Additives */}
      {Array.isArray(product.additives) && product.additives.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Additives</Text>
          {product.additives.map((a, i) => (
            <Text
              key={i}
              style={[
                styles.text,
                a?.risk === "avoid"
                  ? { color: "red" }
                  : a?.risk === "moderate"
                  ? { color: "orange" }
                  : { color: "green" },
              ]}
            >
              • {a?.code} — {a?.name} ({a?.risk})
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

function niceKey(k) {
  return k
    .replace("_g", "")
    .replace("_mg", "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// --- Pantry & Profile placeholders ---
function Blank({ title }) {
  return (
    <View style={styles.center}>
      <Text style={{ fontSize: 22, fontWeight: "600" }}>{title}</Text>
    </View>
  );
}
function Center({ children }) {
  return <View style={styles.center}>{children}</View>;
}

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerTitle: "Score My Food" }}>
        <Tab.Screen name="Home" component={HomeScreen} />
        <Tab.Screen name="Scan" component={ScanScreen} />
        <Tab.Screen name="Pantry" children={() => <Blank title="Pantry" />} />
        <Tab.Screen name="Profile" children={() => <Blank title="Profile" />} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { padding: 16 },
  image: { width: "100%", height: 200, borderRadius: 12 },
  name: { fontSize: 20, fontWeight: "700", marginTop: 10 },
  brand: { opacity: 0.7, marginBottom: 8 },
  score: { fontSize: 16, marginBottom: 8 },
  section: { marginTop: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  text: { fontSize: 14, marginBottom: 2 },
  debug: { fontSize: 12, color: "gray", marginBottom: 6 },
});
