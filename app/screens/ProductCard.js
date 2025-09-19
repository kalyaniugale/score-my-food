import { View, Text, Image, StyleSheet } from "react-native";

export default function ProductCard({ product }) {
  console.log("ProductCard props:", product); // debug log

  if (!product) {
    return (
      <View style={styles.card}>
        <Text>No product data</Text>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      {/* Debug keys always visible */}
      <Text style={{ fontSize: 12, color: "gray", marginBottom: 6 }}>
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
                • {k.replace("_g", "").replace("_mg", "")}: {v}
                {k.includes("mg") ? " mg" : " g"}
              </Text>
            ) : null
          )}
        </View>
      )}

      {/* Positives */}
      {product.positives?.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "green" }]}>
            ✅ Positives
          </Text>
          {product.positives.map((p, i) => (
            <Text key={i} style={styles.text}>• {p}</Text>
          ))}
        </View>
      )}

      {/* Negatives */}
      {product.negatives?.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "red" }]}>
            ⚠️ Negatives
          </Text>
          {product.negatives.map((n, i) => (
            <Text key={i} style={styles.text}>• {n}</Text>
          ))}
        </View>
      )}

      {/* Additives */}
      {product.additives?.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Additives</Text>
          {product.additives.map((a, i) => (
            <Text
              key={i}
              style={[
                styles.text,
                a.risk === "avoid"
                  ? { color: "red" }
                  : a.risk === "moderate"
                  ? { color: "orange" }
                  : { color: "green" },
              ]}
            >
              • {a.code} — {a.name} ({a.risk})
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: 16 },
  image: { width: "100%", height: 180, borderRadius: 12 },
  name: { fontSize: 20, fontWeight: "700", marginTop: 10 },
  brand: { opacity: 0.7, marginBottom: 8 },
  score: { fontSize: 16, marginBottom: 8 },
  section: { marginTop: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  text: { fontSize: 14, marginBottom: 2 },
});
