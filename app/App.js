// app/app.js
import { NavigationContainer, useNavigation } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  ActivityIndicator,
  Button,
  Image,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  Dimensions,
} from "react-native";
import { API } from "./lib/api";
import { CameraView, useCameraPermissions } from "expo-camera";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Modal, Pressable } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import * as ImagePicker from "expo-image-picker";

// Screen A: scan mode chooser
function ScanChooserScreen({ navigation }) {
  return (
    <View style={{ flex: 1, padding: 16, justifyContent: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", textAlign: "center" }}>Scan</Text>
      <Text style={{ color: "#6b7280", textAlign: "center", marginTop: 4 }}>
        Choose what you want to scan
      </Text>

      <View style={{ height: 20 }} />

      <TouchableOpacity
        style={[styles.card, { padding: 16 }]}
        onPress={() => navigation.navigate("BarcodeScan")}
      >
        <Text style={{ fontSize: 18, fontWeight: "700" }}>📦 Scan Barcode</Text>
        <Text style={{ color: "#6b7280", marginTop: 4 }}>Use camera to scan product barcode</Text>
      </TouchableOpacity>

      <View style={{ height: 12 }} />

      <TouchableOpacity
        style={[styles.card, { padding: 16 }]}
        onPress={() => navigation.navigate("IngredientsOCR")}
      >
        <Text style={{ fontSize: 18, fontWeight: "700" }}>📝 Scan Ingredients (OCR)</Text>
        <Text style={{ color: "#6b7280", marginTop: 4 }}>
          Photo of label → extract ingredients → analyze score
        </Text>
      </TouchableOpacity>
    </View>
  );
}

// Screen B: ingredients OCR flow
function IngredientsOCRScreen({ navigation }) {
  const [img, setImg] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState(null);
  const [text, setText] = useState("");

  async function pickImage(fromCamera = false) {
    setError(null);
    try {
      if (fromCamera) {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) {
          setError("Camera permission is required");
          return;
        }
        const shot = await ImagePicker.launchCameraAsync({
          quality: 0.7,
          base64: false,
        });
        if (!shot.canceled) setImg(shot.assets[0]);
      } else {
        const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) {
          setError("Media library permission is required");
          return;
        }
        const sel = await ImagePicker.launchImageLibraryAsync({
          quality: 0.7,
          base64: false,
        });
        if (!sel.canceled) setImg(sel.assets[0]);
      }
    } catch (e) {
      setError(e.message || "Failed to pick image");
    }
  }

  async function runOCRAndAnalyze() {
    if (!img?.uri) {
      setError("Please select or capture a label image first");
      return;
    }
    setExtracting(true);
    setError(null);
    try {
      // POST multipart form to backend
      const form = new FormData();
      form.append("image", {
        uri: img.uri,
        name: "label.jpg",
        type: "image/jpeg",
      });

      // New backend route (see Django code below)
      const res = await API.post("/api/ocr/analyze/", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const analysis = res.data; // should be product-like object
      setText(analysis?.ingredients_text || "");
      // Navigate to the same ProductDetail screen you already use
      navigation.navigate("ProductDetail", {
        code: analysis?.barcode || "ocr-only",
        preview: analysis,
      });
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "OCR failed");
    } finally {
      setExtracting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 20, fontWeight: "800" }}>Scan Ingredients</Text>
        <Text style={{ color: "#6b7280", marginTop: 4 }}>
          Take or upload a clear photo of the ingredients panel.
        </Text>

        <View style={{ height: 16 }} />

        <View style={{ flexDirection: "row", gap: 10 }}>
          <TouchableOpacity style={[styles.searchBtn, { flex: 1 }]} onPress={() => pickImage(true)}>
            <Text style={{ color: "#fff", textAlign: "center", fontWeight: "700" }}>Use Camera</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.card, { flex: 1, alignItems: "center", paddingVertical: 12 }]} onPress={() => pickImage(false)}>
            <Text style={{ fontWeight: "700" }}>Choose from Gallery</Text>
          </TouchableOpacity>
        </View>

        {img?.uri ? (
          <View style={[styles.card, { padding: 10, marginTop: 12 }]}>
            <Image source={{ uri: img.uri }} style={{ width: "100%", height: 250, borderRadius: 12 }} />
          </View>
        ) : null}

        {error ? <Text style={{ color: "red", marginTop: 8 }}>{error}</Text> : null}

        <View style={{ height: 12 }} />

        <TouchableOpacity
          style={[styles.searchBtn, { opacity: img ? 1 : 0.5 }]}
          onPress={runOCRAndAnalyze}
          disabled={!img || extracting}
        >
          {extracting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={{ color: "#fff", textAlign: "center", fontWeight: "700" }}>
              Extract & Analyze
            </Text>
          )}
        </TouchableOpacity>

        {text ? (
          <View style={{ marginTop: 12 }}>
            <Text style={{ fontWeight: "700" }}>Extracted ingredients (preview)</Text>
            <Text style={{ color: "#374151", marginTop: 4 }}>{text}</Text>
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}


/* ------------------------
 * Helpers
 * ------------------------ */
function niceKey(k) {
  return k
    .replace("_mg", "")
    .replace("_g", "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
function unitSuffix(key) {
  if (/_mg$/i.test(key)) return " mg";
  if (/_g$/i.test(key)) return " g";
  if (/kcal/i.test(key)) return " kcal";
  return "";
}
function riskColor(risk) {
  if (risk === "avoid") return { color: "red" };
  if (risk === "moderate") return { color: "orange" };
  if (risk === "safe") return { color: "green" };
  return { color: "#444" };
}
function scoreColor(score) {
  if (score >= 80) return "#2ecc71";
  if (score >= 60) return "#a3d977";
  if (score >= 40) return "#f1c40f";
  if (score >= 20) return "#e67e22";
  return "#e74c3c";
}
const formatINR = (n) => `₹${Math.round(n)}`;


/** in-memory cache (optional) */
const analyzedCache = new Map(); // code -> product
async function fetchAnalyzed(code) {
  if (analyzedCache.has(code)) return analyzedCache.get(code);
  const res = await API.get(`/api/products/${encodeURIComponent(code)}/`);
  const product = res.data;
  analyzedCache.set(code, product);
  return product;
}
async function analyzeInBatches(codes, batchSize = 4) {
  const results = {};
  for (let i = 0; i < codes.length; i += batchSize) {
    const slice = codes.slice(i, i + batchSize);
    const settled = await Promise.allSettled(slice.map((c) => fetchAnalyzed(c)));
    settled.forEach((s, idx) => {
      const code = slice[idx];
      if (s.status === "fulfilled") results[code] = s.value;
    });
  }
  return results;
}

/* ------------------------
 * Product Card (detail)
 * ------------------------ */
function ProductCard({ product }) {
  if (!product) return <View style={styles.card}><Text>No product data</Text></View>;

  return (
    <View style={[styles.card, { padding: 16 }]}>
      {product.image ? (
        <Image source={{ uri: product.image }} style={styles.image} />
      ) : null}

      <Text style={styles.name}>{product.name}</Text>
      <Text style={styles.brand}>{product.brand || "—"}</Text>

      {"score" in product && (
        <View style={[styles.detailScoreWrap, { backgroundColor: scoreColor(product.score ?? 0) }]}>
          <Text style={styles.detailScoreText}>Score: {product.score}/100</Text>
        </View>
      )}

      {product.ingredients_text ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Ingredients</Text>
          <Text style={styles.text}>{product.ingredients_text}</Text>
        </View>
      ) : null}

      {product.nutrition && Object.keys(product.nutrition).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Nutrition (per 100g)</Text>
          {Object.entries(product.nutrition).map(([k, v]) =>
            v != null ? (
              <Text key={k} style={styles.text}>
                • {niceKey(k)}: {String(v)}
                {unitSuffix(k)}
              </Text>
            ) : null
          )}
        </View>
      )}

      {Array.isArray(product.positives) && product.positives.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "green" }]}>✅ Positives</Text>
          {product.positives.map((p, i) => (
            <Text key={i} style={styles.text}>• {p}</Text>
          ))}
        </View>
      )}

      {Array.isArray(product.negatives) && product.negatives.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: "red" }]}>⚠️ Negatives</Text>
          {product.negatives.map((n, i) => (
            <Text key={i} style={styles.text}>• {n}</Text>
          ))}
        </View>
      )}

      {Array.isArray(product.additives) && product.additives.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Additives</Text>
          {product.additives.map((a, i) => (
            <Text key={i} style={[styles.text, riskColor(a?.risk)]}>
              • {a?.code}{a?.name ? ` — ${a.name}` : ""} {a?.risk ? `(${a.risk})` : ""}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

/* ------------------------
 * Product Detail Screen — shows "Analyzing…" while fetching
 * ------------------------ */
function ProductDetailScreen({ route }) {
  const { code, preview } = route.params || {};
  const [product, setProduct] = useState(preview || null);
  const [analyzing, setAnalyzing] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setAnalyzing(true);
        const res = await API.get(`/api/products/${encodeURIComponent(code)}/`);
        if (!cancelled) setProduct(res.data);
      } catch (e) {
        if (!cancelled) {
          setErr(
            e?.response?.data?.detail ||
            e?.response?.data?.error ||
            e?.message ||
            "Error"
          );
        }
      } finally {
        if (!cancelled) setAnalyzing(false);
      }
    })();
    return () => { cancelled = true; };
  }, [code]);

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
      {analyzing && (
        <View style={styles.analyzingBanner}>
          <ActivityIndicator />
          <Text style={styles.analyzingText}>Analyzing… pulling ingredients & score</Text>
        </View>
      )}
      {err && !product ? (
        <Center><Text>❌ {err}</Text></Center>
      ) : (
        <ProductCard product={product} />
      )}
    </ScrollView>
  );
}

/* ------------------------
 * Home Screen (cards clickable; list pre-analyzed)
 * ------------------------ */
const CATEGORY_PRESETS = [
  { key: "snacks", title: "Snacks", offTag: "snacks" },
  { key: "breakfast-cereals", title: "Breakfast cereals", offTag: "breakfast-cereals" },
  { key: "yogurts", title: "Yogurts", offTag: "yogurts" },
  { key: "beverages", title: "Beverages", offTag: "beverages" },
];
const CARD_W = Math.min(220, Math.round(Dimensions.get("window").width * 0.6));

function HomeScreen() {
  const [ping, setPing] = useState(null);
  const [q, setQ] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]); // analyzed items
  const [sections, setSections] = useState(
    CATEGORY_PRESETS.map((c) => ({ ...c, loading: true, error: null, items: [] }))
  );

  useEffect(() => {
    (async () => {
      try {
        const r = await API.get("/api/ping");
        setPing(r.data?.ok ? "✅ Connected" : "⚠️ Ping failed");
      } catch (e) {
        setPing("❌ " + (e?.message || "Error"));
      }
    })();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next = await Promise.all(
        sections.map(async (sec) => {
          try {
            const url =
              `https://world.openfoodfacts.org/category/${encodeURIComponent(sec.offTag)}.json` +
              `?page_size=12&fields=product_name,brands,image_front_url,image_url,` +
              `nutriments,code`;
            const r = await fetch(url, { headers: { "User-Agent": "score-my-food/1.0" } });
            const data = await r.json();
            const raw = (data?.products || [])
              .map((p) => ({
                code: p.code,
                name: p.product_name || "Unnamed",
                brand: (p.brands || "").split(",")[0].trim(),
                image: p.image_front_url || p.image_url || null,
              }))
              .filter((p) => p.image && p.code);

            const codes = raw.map((p) => p.code);
            const analyzedMap = await analyzeInBatches(codes, 4);
            const items = raw.map((p) => analyzedMap[p.code] || { ...p });
            return { ...sec, loading: false, items };
          } catch (e) {
            return { ...sec, loading: false, error: e?.message || "Failed", items: [] };
          }
        })
      );
      if (!cancelled) setSections(next);
    })();
    return () => { cancelled = true; };
  }, []);

  const onSearch = async () => {
    const query = q.trim();
    if (!query) return;
    setIsSearching(true);
    setResults([]);
    try {
      const url =
        `https://world.openfoodfacts.org/cgi/search.pl?search_terms=${encodeURIComponent(query)}` +
        `&search_simple=1&json=1&page_size=20&fields=product_name,brands,image_front_url,image_url,nutriments,code`;
      const r = await fetch(url, { headers: { "User-Agent": "score-my-food/1.0" } });
      const data = await r.json();
      const raw = (data?.products || [])
        .map((p) => ({
          code: p.code,
          name: p.product_name || "Unnamed",
          brand: (p.brands || "").split(",")[0].trim(),
          image: p.image_front_url || p.image_url || null,
        }))
        .filter((p) => p.image && p.code);

      const codes = raw.map((p) => p.code);
      const analyzedMap = await analyzeInBatches(codes, 4);
      const analyzedItems = raw.map((p) => analyzedMap[p.code] || { ...p });
      setResults(analyzedItems);
    } catch (e) {
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={styles.hero}>
        <Text style={styles.appTitle}>🍽️ Score My Food</Text>
        <Text style={styles.subtitle}>Scan, search, and pick better bites.</Text>

        <View style={styles.searchRow}>
          <TextInput
            placeholder="Search snacks, cereals, yogurt..."
            value={q}
            onChangeText={setQ}
            onSubmitEditing={onSearch}
            style={styles.searchInput}
            returnKeyType="search"
          />
          <TouchableOpacity style={styles.searchBtn} onPress={onSearch}>
            <Text style={{ color: "white", fontWeight: "700" }}>Search</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.pill}>
          {!ping ? <ActivityIndicator /> : <Text style={styles.pillText}>{ping}</Text>}
        </View>
      </View>

      {isSearching ? (
        <View style={{ paddingHorizontal: 16, paddingTop: 8 }}>
          <Text style={styles.sectionTitle}>{`Searching "${q}"`}</Text>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            data={Array.from({ length: 6 }).map((_, i) => ({ id: "s" + i }))}
            keyExtractor={(i) => i.id}
            renderItem={() => <SkeletonCard width={CARD_W} />}
            ItemSeparatorComponent={() => <View style={{ width: 12 }} />}
            contentContainerStyle={{ paddingVertical: 8 }}
          />
        </View>
      ) : results.length > 0 ? (
       <CarouselSection title={`Results for "${q}"`} items={results} />
      ) : null}

      {sections.map((sec) => (
        <View key={sec.key}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>{sec.title}</Text>
            <TouchableOpacity onPress={() => {}}>
              <Text style={styles.sectionSeeAll}>See all</Text>
            </TouchableOpacity>
          </View>

          {sec.loading ? (
            <FlatList
              horizontal
              showsHorizontalScrollIndicator={false}
              data={Array.from({ length: 6 }).map((_, i) => ({ id: sec.key + i }))}
              keyExtractor={(i) => i.id}
              renderItem={() => <SkeletonCard width={CARD_W} />}
              ItemSeparatorComponent={() => <View style={{ width: 12 }} />}
              contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 8 }}
            />
          ) : sec.error ? (
            <View style={{ paddingHorizontal: 16, paddingVertical: 8 }}>
              <Text style={{ color: "red" }}>Failed to load: {sec.error}</Text>
            </View>
          ) : (
            <CarouselSection title={null} items={sec.items} />
          )}
        </View>
      ))}
    </ScrollView>
  );
}

function CarouselSection({ title, items }) {
  return (
    <View style={{ marginTop: 4 }}>
      {title ? (
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{title}</Text>
        </View>
      ) : null}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={items}
        keyExtractor={(item, idx) => item.barcode || item.code || String(idx)}
        renderItem={({ item }) => <ProductTile item={item} />}
        ItemSeparatorComponent={() => <View style={{ width: 12 }} />}
        contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 8 }}
      />
    </View>
  );
}

function ProductTile({ item }) {
  const navigation = useNavigation();
  const code = item.barcode || item.code;

  const onPress = () => {
    navigation.navigate("ProductDetail", {
      code,
      preview: {
        barcode: code,
        name: item.name,
        brand: item.brand,
        image: item.image,
        score: typeof item.score === "number" ? item.score : undefined,
      },
    });
  };

  const score = item.score ?? (item.nutrition?.score);
  return (
    <TouchableOpacity activeOpacity={0.85} style={[styles.card, { width: CARD_W }]} onPress={onPress}>
      <View style={styles.imageWrap}>
        {item.image ? (
          <Image source={{ uri: item.image }} style={styles.image} />
        ) : (
          <View style={[styles.image, styles.imagePlaceholder]}>
            <Text style={{ color: "#777" }}>No image</Text>
          </View>
        )}
        {typeof score === "number" && (
          <View style={[styles.scoreBadge, { backgroundColor: scoreColor(score) }]}>
            <Text style={styles.scoreText}>{score}</Text>
          </View>
        )}
      </View>
      <Text numberOfLines={1} style={styles.cardName}>
        {item.name}
      </Text>
      <Text numberOfLines={1} style={styles.cardBrand}>
        {item.brand || "—"}
      </Text>
    </TouchableOpacity>
  );
}

function SkeletonCard({ width }) {
  return (
    <View style={[styles.card, { width }]}>
      <View style={[styles.image, { backgroundColor: "#f1f1f1" }]} />
      <View style={{ height: 10 }} />
      <View style={{ width: width * 0.8, height: 14, backgroundColor: "#eee", borderRadius: 6 }} />
      <View style={{ height: 6 }} />
      <View style={{ width: width * 0.5, height: 12, backgroundColor: "#f0f0f0", borderRadius: 6 }} />
    </View>
  );
}

/* ------------------------
 * PANTRY — Grocery List Builder
 * ------------------------ */
function PantryScreen() {
  const navigation = useNavigation();   // ✅ use navigation hook
  const [input, setInput] = useState("bread, yogurt, eggs, cereal, juice");
  const [budget, setBudget] = useState("800"); // ₹
  const [loading, setLoading] = useState(false);
  const [candidates, setCandidates] = useState({});
  const [basket, setBasket] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  // heuristic price estimation (₹) — tweak as needed
  const estimatePrice = (name = "", brand = "", score = 50) => {
    const n = name.toLowerCase();
    let base =
      n.includes("rice") || n.includes("dal") ? 120 :
      n.includes("yogurt") || n.includes("curd") ? 60 :
      n.includes("milk") ? 65 :
      n.includes("bread") ? 45 :
      n.includes("egg") ? 70 :
      n.includes("oats") || n.includes("cereal") ? 180 :
      n.includes("juice") ? 110 :
      n.includes("snack") || n.includes("chips") ? 40 :
      100;
    if (brand) base += 20;
    base += (Math.max(0, score - 50) / 50) * 40;
    return Math.round(base);
  };

  const parseTerms = () =>
    input
      .split(",")
      .map(t => t.trim())
      .filter(Boolean)
      .slice(0, 10);

  const searchTerm = async (term) => {
    const url =
      `https://world.openfoodfacts.org/cgi/search.pl?search_terms=${encodeURIComponent(term)}` +
      `&search_simple=1&json=1&page_size=12&fields=product_name,brands,image_front_url,image_url,code`;
    const r = await fetch(url, { headers: { "User-Agent": "score-my-food/1.0" } });
    const data = await r.json();
    const raw = (data?.products || [])
      .map((p) => ({
        code: p.code,
        name: p.product_name || "Unnamed",
        brand: (p.brands || "").split(",")[0].trim(),
        image: p.image_front_url || p.image_url || null,
      }))
      .filter((p) => p.image && p.code);

    const codes = raw.map(p => p.code);
    const analyzedMap = await analyzeInBatches(codes, 4);
    const analyzed = raw
      .map(p => analyzedMap[p.code] || { ...p, score: 50, positives: [], negatives: [] })
      .map(p => ({ ...p, price: estimatePrice(p.name, p.brand, p.score ?? 50), term }));
    analyzed.sort((a,b) => (b.score ?? 0) - (a.score ?? 0));
    return analyzed;
  };

  const buildBasket = (byTerm, maxBudget) => {
    const terms = Object.keys(byTerm);
    let chosen = terms.map(t => byTerm[t][0]).filter(Boolean);
    const totalPrice = () => chosen.reduce((s, p) => s + (p.price || 0), 0);
    const avgScore = () =>
      chosen.length ? Math.round(chosen.reduce((s, p) => s + (p.score ?? 0), 0) / chosen.length) : 0;

    while (totalPrice() > maxBudget) {
      let bestSwap = null;
      for (const t of terms) {
        const list = byTerm[t];
        const curr = chosen.find(p => p.term === t);
        if (!curr) continue;
        const idx = list.findIndex(p => p.code === curr.code);
        if (idx < 0 || idx === list.length - 1) continue;
        const next = list[idx + 1];
        const deltaPrice = (curr.price || 0) - (next.price || 0);
        const deltaScore = (curr.score ?? 0) - (next.score ?? 0);
        const scorePerRupee = deltaPrice > 0 ? deltaScore / deltaPrice : Infinity;
        if (!bestSwap || scorePerRupee < bestSwap.scorePerRupee) {
          bestSwap = { t, next, idx, scorePerRupee };
        }
      }
      if (!bestSwap) break;
      chosen = chosen.map(p => (p.term === bestSwap.t ? byTerm[bestSwap.t][bestSwap.idx + 1] : p));
    }

    return {
      chosen,
      total: totalPrice(),
      avgScore: avgScore(),
      missing: terms.filter(t => !chosen.find(p => p.term === t)),
    };
  };

  const onBuild = async () => {
    const terms = parseTerms();
    if (!terms.length) {
      setError("Please add at least one item");
      return;
    }
    setError(null);
    setLoading(true);
    setCandidates({});
    setBasket([]);
    setSummary(null);
    try {
      const entries = await Promise.all(
        terms.map(async (t) => [t, await searchTerm(t)])
      );
      const byTerm = Object.fromEntries(entries);
      setCandidates(byTerm);

      const maxBudget = Math.max(0, parseInt(budget || "0", 10));
      const res = buildBasket(byTerm, maxBudget);
      setBasket(res.chosen);
      setSummary({ total: res.total, avgScore: res.avgScore, missing: res.missing });
    } catch (e) {
      setError(e?.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={styles.hero}>
        <Text style={styles.appTitle}>🧺 Grocery List Builder</Text>
        <Text style={styles.subtitle}>
          Type items + set a budget. I’ll pick the healthiest basket within ₹.
        </Text>
      </View>

      <View style={{ paddingHorizontal: 16, gap: 10 }}>
        <TextInput
          placeholder="e.g., bread, yogurt, eggs, cereal, juice"
          value={input}
          onChangeText={setInput}
          style={styles.searchInput}
        />
        <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          <TextInput
            placeholder="Budget (₹)"
            value={budget}
            onChangeText={setBudget}
            keyboardType="numeric"
            style={[styles.searchInput, { flex: 0.5 }]}
          />
          <TouchableOpacity
            style={[styles.searchBtn, { flex: 0.5 }]}
            onPress={onBuild}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={{ color: "white", fontWeight: "700", textAlign: "center" }}>
                Build Basket
              </Text>
            )}
          </TouchableOpacity>
        </View>
        {error ? <Text style={{ color: "red" }}>{error}</Text> : null}
      </View>

      {summary && (
        <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
          <View
            style={[
              styles.card,
              {
                padding: 14,
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
              },
            ]}
          >
            <Text style={{ fontWeight: "700" }}>Basket</Text>
            <Text>
              Avg Score:{" "}
              <Text style={{ fontWeight: "800", color: scoreColor(summary.avgScore) }}>
                {summary.avgScore}
              </Text>
            </Text>
            <Text>
              Total: <Text style={{ fontWeight: "800" }}>{formatINR(summary.total)}</Text>
            </Text>
          </View>
          {summary.missing?.length ? (
            <Text style={{ color: "#6b7280", marginTop: 6 }}>
              No good matches for: {summary.missing.join(", ")}
            </Text>
          ) : null}
        </View>
      )}

      <View style={{ paddingHorizontal: 16, paddingTop: 8 }}>
        {loading && (
          <View style={[styles.card, { padding: 14, alignItems: "center" }]}>
            <ActivityIndicator />
            <Text style={{ marginTop: 8 }}>Searching & analyzing items…</Text>
          </View>
        )}

        {!loading &&
          basket.map((p) => (
            <View
              key={p.code}
              style={[
                styles.card,
                {
                  padding: 10,
                  flexDirection: "row",
                  gap: 12,
                  alignItems: "center",
                  marginBottom: 10,
                },
              ]}
            >
              <Image
                source={{ uri: p.image }}
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 10,
                  backgroundColor: "#f3f4f6",
                }}
              />
              <View style={{ flex: 1 }}>
                <Text numberOfLines={1} style={{ fontWeight: "700" }}>
                  {p.name}
                </Text>
                <Text numberOfLines={1} style={{ color: "#6b7280" }}>
                  {p.brand || "—"}
                </Text>
                <Text style={{ marginTop: 4 }}>
                  Score:{" "}
                  <Text style={{ fontWeight: "800", color: scoreColor(p.score ?? 0) }}>
                    {p.score ?? "-"}
                  </Text>{" "}
                  · {formatINR(p.price)}
                </Text>
                {Array.isArray(p.positives) && p.positives.length > 0 ? (
                  <Text numberOfLines={1} style={{ color: "green" }}>
                    + {p.positives[0]}
                  </Text>
                ) : null}
                {Array.isArray(p.negatives) && p.negatives.length > 0 ? (
                  <Text numberOfLines={1} style={{ color: "red" }}>
                    – {p.negatives[0]}
                  </Text>
                ) : null}
              </View>
              <TouchableOpacity
                onPress={() => {
                  // ✅ navigate to same ProductDetail as Home cards
                  navigation.navigate("ProductDetail", { code: p.code, preview: p });
                }}
                style={{
                  paddingHorizontal: 10,
                  paddingVertical: 8,
                  backgroundColor: "#111",
                  borderRadius: 10,
                }}
              >
                <Text style={{ color: "#fff", fontWeight: "700" }}>Details</Text>
              </TouchableOpacity>
            </View>
          ))}
      </View>
    </ScrollView>
  );
}
function ProfileScreen() {
  const [profile, setProfile] = useState({
    displayName: "Demo User",
    handle: "@guest",
    tagline: "Making smarter food choices.",
    diet: "None",
    quote: "\"Eat better, feel better.\"",
    avatar: "🥕", // keep carrot as profile
  });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(profile);
  const [loading, setLoading] = useState(true);

  async function loadProfile() {
    try {
      const raw = await AsyncStorage.getItem("smf_profile");
      if (raw) {
        const saved = JSON.parse(raw);
        setProfile(saved);
        setForm(saved);
      }
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    loadProfile();
  }, []);

  // refresh when the tab gains focus
  useFocusEffect(
    React.useCallback(() => {
      loadProfile();
    }, [])
  );

  function startEdit() {
    setForm(profile);
    setEditing(true);
  }

  async function saveEdit() {
    const cleaned = {
      displayName: (form.displayName || "").trim() || "Demo User",
      handle: (form.handle || "").trim() || "@guest",
      tagline: (form.tagline || "").trim(),
      diet: (form.diet || "").trim() || "None",
      quote: (form.quote || "").trim(),
      avatar: (form.avatar || "🥕").trim() || "🥕",
    };
    setProfile(cleaned);
    setEditing(false);
    try {
      await AsyncStorage.setItem("smf_profile", JSON.stringify(cleaned));
    } catch {}
  }

  function clearAnalysisCache() {
    try {
      if (typeof analyzedCache?.clear === "function") analyzedCache.clear();
    } catch {}
  }

  if (loading) {
    return (
      <Center>
        <ActivityIndicator />
      </Center>
    );
  }

  // demo metrics (wire to real data later if you want)
  const metrics = [
    { label: "Streak", value: "3 days" },
    { label: "Avg Score", value: "72" },
    { label: "Scanned", value: "18" },
  ];

  const badges = [
    { icon: "🔥", title: "Streak Starter", sub: "3 days active" },
    { icon: "🥗", title: "Health Curious", sub: "Avg 70+ score" },
    { icon: "🧠", title: "Label Reader", sub: "Checks additives" },
    { icon: "⚡", title: "Quick Scanner", sub: "Fast lookups" },
    { icon: "🌿", title: "Plant Friendly", sub: "Prefers clean picks" },
  ];

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
      {/* Header */}
      <View style={[styles.hero, { alignItems: "center" }]}>
        <View style={styles.avatarCircle}>
          <Text style={{ fontSize: 42 }}>{profile.avatar}</Text>
        </View>
        <Text style={[styles.appTitle, { marginTop: 8 }]}>{profile.displayName}</Text>
        <Text style={{ color: "#6b7280", marginTop: 2 }}>{profile.handle}</Text>

        {profile.tagline ? (
          <Text style={{ marginTop: 6, fontWeight: "600" }}>{profile.tagline}</Text>
        ) : null}

        {profile.diet ? (
          <View style={[styles.pill, { marginTop: 10 }]}>
            <Text style={styles.pillText}>{profile.diet}</Text>
          </View>
        ) : null}

        <TouchableOpacity style={styles.editBtn} onPress={startEdit}>
          <Text style={{ color: "#111", fontWeight: "700" }}>Edit Profile</Text>
        </TouchableOpacity>
      </View>

      {/* Metrics row */}
      <View style={{ paddingHorizontal: 16 }}>
        <View style={styles.metricRow}>
          {metrics.map((m, i) => (
            <View key={i} style={styles.metricCard}>
              <Text style={styles.metricValue}>{m.value}</Text>
              <Text style={styles.metricLabel}>{m.label}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Quote */}
      {profile.quote ? (
        <View style={[styles.card, { marginHorizontal: 16, padding: 16, marginTop: 12 }]}>
          <Text style={{ fontStyle: "italic" }}>{profile.quote}</Text>
        </View>
      ) : null}

      {/* Horizontal badges */}
      <View style={{ paddingTop: 12 }}>
        <Text style={[styles.sectionTitle, { paddingHorizontal: 16 }]}>Badges</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.hScroll}
        >
          {badges.map((b, i) => (
            <View key={i} style={styles.badgeCard}>
              <Text style={styles.badgeIcon}>{b.icon}</Text>
              <Text style={styles.badgeTitle}>{b.title}</Text>
              <Text style={styles.badgeSubtitle}>{b.sub}</Text>
            </View>
          ))}
        </ScrollView>
      </View>

      {/* Utilities */}
      <View style={{ paddingHorizontal: 16, paddingTop: 12, gap: 10 }}>
        <TouchableOpacity style={[styles.card, { padding: 14 }]} onPress={clearAnalysisCache}>
          <Text style={{ fontWeight: "700" }}>Clear analyzed product cache</Text>
          <Text style={{ color: "#6b7280" }}>
            Frees memory and forces re-analysis next time.
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.card, { padding: 14 }]}
          onPress={async () => {
            const demo = {
              displayName: "Demo User",
              handle: "@guest",
              tagline: "Making smarter food choices.",
              diet: "None",
              quote: "\"Eat better, feel better.\"",
              avatar: "🥕",
            };
            setProfile(demo);
            setForm(demo);
            try {
              await AsyncStorage.setItem("smf_profile", JSON.stringify(demo));
            } catch {}
          }}
        >
          <Text style={{ fontWeight: "700" }}>Reset to demo</Text>
          <Text style={{ color: "#6b7280" }}>Restore the default demo profile.</Text>
        </TouchableOpacity>
      </View>

      {/* Edit Modal */}
      <Modal visible={editing} animationType="slide" transparent>
        <Pressable style={styles.modalBackdrop} onPress={() => setEditing(false)} />
        <View style={styles.modalSheet}>
          <Text style={{ fontSize: 18, fontWeight: "800", marginBottom: 10 }}>Edit Profile</Text>

          <TextInput
            placeholder="Display name"
            value={form.displayName}
            onChangeText={(t) => setForm((s) => ({ ...s, displayName: t }))}
            style={styles.input}
          />
          <TextInput
            placeholder="@handle"
            value={form.handle}
            onChangeText={(t) => setForm((s) => ({ ...s, handle: t }))}
            autoCapitalize="none"
            style={styles.input}
          />
          <TextInput
            placeholder="Tagline"
            value={form.tagline}
            onChangeText={(t) => setForm((s) => ({ ...s, tagline: t }))}
            style={styles.input}
          />
          <TextInput
            placeholder="Diet (e.g., Vegetarian, Vegan, None)"
            value={form.diet}
            onChangeText={(t) => setForm((s) => ({ ...s, diet: t }))}
            style={styles.input}
          />
          <TextInput
            placeholder="Favorite quote"
            value={form.quote}
            onChangeText={(t) => setForm((s) => ({ ...s, quote: t }))}
            style={styles.input}
          />
          <TextInput
            placeholder="Avatar emoji (e.g., 🥕)"
            value={form.avatar}
            onChangeText={(t) => setForm((s) => ({ ...s, avatar: t }))}
            style={styles.input}
          />

          <View style={{ flexDirection: "row", gap: 10, marginTop: 8 }}>
            <TouchableOpacity style={[styles.searchBtn, { flex: 1 }]} onPress={saveEdit}>
              <Text style={{ color: "white", fontWeight: "700", textAlign: "center" }}>Save</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.card,
                { paddingHorizontal: 16, paddingVertical: 12, flex: 1, alignItems: "center" },
              ]}
              onPress={() => setEditing(false)}
            >
              <Text style={{ fontWeight: "700" }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

/* ------------------------
 * Scan Screen (UNCHANGED)
 * ------------------------ */
function ScanScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [product, setProduct] = useState(null);
  const [error, setError] = useState(null);
  const scanLock = useRef(false);

  useEffect(() => {
    if (permission?.granted === false || permission == null) {
      requestPermission();
    }
  }, []); // once

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
    if (scanLock.current || scanned) return;
    scanLock.current = true;

    setScanned(true);
    setLoading(true);
    setError(null);
    setProduct(null);

    try {
      const res = await API.get(`/api/products/${encodeURIComponent(data)}/`);
      setProduct(res.data);
    } catch (e) {
      const detail =
        e?.response?.data?.detail || e?.response?.data?.error || e?.message || "Error";
      setError(detail);
    } finally {
      setLoading(false);
      setTimeout(() => { scanLock.current = false; }, 500);
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
const ScanStackNav = createNativeStackNavigator();

function ScanStack() {
  return (
    <ScanStackNav.Navigator
      screenOptions={{
        headerTitle: "",                  // no header title text
        headerBackTitleVisible: false,    // hide "Back" label on iOS
        headerShadowVisible: false,       // remove bottom border/shadow
        contentStyle: { backgroundColor: "#fff" }, // consistent background
      }}
    >
      <ScanStackNav.Screen
        name="ScanChooser"
        component={ScanChooserScreen}
      />
      <ScanStackNav.Screen
        name="BarcodeScan"
        component={ScanScreen}
      />
      <ScanStackNav.Screen
        name="IngredientsOCR"
        component={IngredientsOCRScreen}
      />
    </ScanStackNav.Navigator>
  );
}

/* ------------------------
 * Blanks + Navigation
 * ------------------------ */
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
const Stack = createNativeStackNavigator();

// global ref so Pantry "Details" button can open Product screen too
let navigationRefObj = null;
function setNavRef(ref) { navigationRefObj = ref; }
const navigationRef = new Proxy({}, { get: () => navigationRefObj });

function Tabs() {
  return (
    <Tab.Navigator screenOptions={{ headerTitle: "Score My Food" }}>
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="Scan" component={ScanStack} />
      <Tab.Screen name="Pantry" component={PantryScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <NavigationContainer
      ref={(r) => setNavRef(r)}
    >
      <Stack.Navigator>
        <Stack.Screen
          name="Root"
          component={Tabs}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="ProductDetail"
          component={ProductDetailScreen}
          options={{ title: "Product" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

/* ------------------------
 * Styles
 * ------------------------ */
const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },

  hero: {
    paddingTop: 24,
    paddingBottom: 16,
    paddingHorizontal: 16,
    backgroundColor: "#fff",
  },
  appTitle: { fontSize: 28, fontWeight: "800" },
  subtitle: { marginTop: 4, color: "#666" },

  searchRow: {
    marginTop: 14,
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
  },
  searchInput: {
    flex: 1,
    backgroundColor: "#f6f6f8",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
  },
  searchBtn: {
    backgroundColor: "#111",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
  },
  pill: {
    marginTop: 12,
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "#f1f5f9",
    borderRadius: 999,
  },
  pillText: { color: "#334155", fontWeight: "600" },

  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sectionTitle: { fontSize: 18, fontWeight: "700" },
  sectionSeeAll: { color: "#6b7280", fontWeight: "600" },

  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 10,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  imageWrap: { position: "relative" },
  image: {
    width: "100%",
    height: 150,
    borderRadius: 12,
    resizeMode: "cover",
    backgroundColor: "#f3f4f6",
  },
  imagePlaceholder: { alignItems: "center", justifyContent: "center" },
  cardName: { marginTop: 8, fontWeight: "700" },
  cardBrand: { color: "#6b7280" },

  scoreBadge: {
    position: "absolute",
    right: 8,
    top: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
  },
  scoreText: { color: "white", fontWeight: "800" },

  name: { fontSize: 20, fontWeight: "700", marginTop: 10 },
  brand: { opacity: 0.7, marginBottom: 8 },

  detailScoreWrap: {
    alignSelf: "flex-start",
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  detailScoreText: { color: "white", fontWeight: "800" },

  score: { fontSize: 16, marginBottom: 8 },
  section: { marginTop: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  text: { fontSize: 14, marginBottom: 2 },
  debug: { fontSize: 12, color: "gray", marginBottom: 6 },

  analyzingBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    margin: 16,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: "#f1f5f9",
  },
  analyzingText: { fontWeight: "600", color: "#334155" },
   avatarCircle: {
   width: 84, height: 84, borderRadius: 42,
   alignItems: "center", justifyContent: "center",
   backgroundColor: "#f1f5f9",
 },
 editBtn: {
   marginTop: 12,
   backgroundColor: "#fff",
   paddingHorizontal: 14, paddingVertical: 10,
   borderRadius: 12,
   borderColor: "#e5e7eb", borderWidth: 1,
 },
 badge: {
   flexDirection: "row",
   alignItems: "center",
   gap: 6,
   backgroundColor: "#fff",
   borderRadius: 12,
   paddingHorizontal: 10, paddingVertical: 8,
   shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
  elevation: 2,
 },
badgeLabel: { fontWeight: "600", color: "#374151" },
 modalBackdrop: {
   flex: 1, backgroundColor: "rgba(0,0,0,0.25)",
 },
 modalSheet: {
   position: "absolute", left: 0, right: 0, bottom: 0,
   backgroundColor: "#fff",
   borderTopLeftRadius: 16, borderTopRightRadius: 16,
   padding: 16,
   shadowColor: "#000", shadowOpacity: 0.2, shadowRadius: 12,
 },
 input: {
   backgroundColor: "#f6f6f8",
   borderRadius: 12,
   paddingHorizontal: 14, paddingVertical: 12,
   marginTop: 8,
},
avatarCircle: {
  width: 84,
  height: 84,
  borderRadius: 42,
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#f1f5f9",
},

editBtn: {
  marginTop: 12,
  backgroundColor: "#fff",
  paddingHorizontal: 14,
  paddingVertical: 10,
  borderRadius: 12,
  borderColor: "#e5e7eb",
  borderWidth: 1,
},

metricRow: {
  flexDirection: "row",
  gap: 10,
  marginTop: 8,
},
metricCard: {
  flex: 1,
  backgroundColor: "#fff",
  borderRadius: 14,
  paddingVertical: 12,
  alignItems: "center",
  shadowColor: "#000",
  shadowOpacity: 0.05,
  shadowRadius: 6,
  shadowOffset: { width: 0, height: 3 },
  elevation: 2,
},
metricValue: { fontSize: 16, fontWeight: "800" },
metricLabel: { color: "#6b7280", marginTop: 2, fontWeight: "600" },

hScroll: {
  paddingHorizontal: 16,
  paddingVertical: 12,
  gap: 12,
},
badgeCard: {
  width: 160,
  backgroundColor: "#fff",
  borderRadius: 14,
  padding: 14,
  marginRight: 12,
  shadowColor: "#000",
  shadowOpacity: 0.05,
  shadowRadius: 6,
  shadowOffset: { width: 0, height: 3 },
  elevation: 2,
},
badgeIcon: { fontSize: 24, marginBottom: 6 },
badgeTitle: { fontWeight: "800" },
badgeSubtitle: { color: "#6b7280", marginTop: 2 },

modalBackdrop: {
  flex: 1,
  backgroundColor: "rgba(0,0,0,0.25)",
},
modalSheet: {
  position: "absolute",
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: "#fff",
  borderTopLeftRadius: 16,
  borderTopRightRadius: 16,
  padding: 16,
  shadowColor: "#000",
  shadowOpacity: 0.2,
  shadowRadius: 12,
},
input: {
  backgroundColor: "#f6f6f8",
  borderRadius: 12,
  paddingHorizontal: 14,
  paddingVertical: 12,
  marginTop: 8,
},


});
