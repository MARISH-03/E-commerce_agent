"""
AI E-Commerce Customer Support Agent  --  SINGLE FILE VERSION
================================================================
Run this file directly in the terminal:
    python ecommerce_agent_all_in_one.py

Everything is in ONE file:
  - Product & order data (embedded, no separate JSON files needed)
  - Tools: search_product, check_order_status, process_return, recommend_products
  - Memory: remembers name/preferences/past order lookups across runs
            (saved to memory_store.json, auto-created next to this file)
  - Main terminal chat loop

If ANTHROPIC_API_KEY environment variable is set, it uses Claude with real
tool-calling. Otherwise it runs a rule-based offline engine (works with no
API key / no internet).
"""

import os
import re
import json

# ======================================================================
# 1. DATA  (in real projects this would be a database; here it's embedded)
# ======================================================================

PRODUCTS = [
    {"id": "P001", "name": "Wireless Bluetooth Earbuds", "category": "Electronics",
     "price": 1999, "stock": 25, "rating": 4.3,
     "description": "Noise-cancelling wireless earbuds with 24hr battery life."},
    {"id": "P002", "name": "Smart Fitness Watch", "category": "Electronics",
     "price": 3499, "stock": 12, "rating": 4.1,
     "description": "Tracks heart rate, sleep, and steps. Water resistant."},
    {"id": "P003", "name": "Men's Running Shoes", "category": "Footwear",
     "price": 1499, "stock": 40, "rating": 4.5,
     "description": "Lightweight breathable running shoes."},
    {"id": "P004", "name": "Women's Casual Sneakers", "category": "Footwear",
     "price": 1299, "stock": 30, "rating": 4.4,
     "description": "Comfortable everyday sneakers."},
    {"id": "P005", "name": "Stainless Steel Water Bottle", "category": "Home & Kitchen",
     "price": 499, "stock": 60, "rating": 4.6,
     "description": "Keeps drinks cold for 24 hours, hot for 12 hours."},
    {"id": "P006", "name": "Laptop Backpack", "category": "Accessories",
     "price": 999, "stock": 18, "rating": 4.2,
     "description": "Water-resistant backpack with padded laptop compartment."},
]

ORDERS = [
    {"order_id": "ORD1001", "customer_name": "Arun Kumar", "product_id": "P001",
     "product_name": "Wireless Bluetooth Earbuds", "status": "Shipped",
     "order_date": "2026-09-01", "expected_delivery": "2026-09-12", "amount": 1999},
    {"order_id": "ORD1002", "customer_name": "Priya Ravi", "product_id": "P003",
     "product_name": "Men's Running Shoes", "status": "Delivered",
     "order_date": "2026-08-25", "expected_delivery": "2026-08-30", "amount": 1499},
    {"order_id": "ORD1003", "customer_name": "Karthik S", "product_id": "P002",
     "product_name": "Smart Fitness Watch", "status": "Processing",
     "order_date": "2026-09-08", "expected_delivery": "2026-09-15", "amount": 3499},
]

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_store.json")


# ======================================================================
# 2. TOOLS  (the actions the agent can take -> "Tool Calling" capability)
# ======================================================================

def search_product(query: str):
    """Search products by name, category, or keyword in description."""
    query = query.lower().strip()
    return [p for p in PRODUCTS
            if query in p["name"].lower()
            or query in p["category"].lower()
            or query in p["description"].lower()]


def check_order_status(order_id: str):
    """Look up an order by its ID."""
    order_id = order_id.strip().upper()
    for o in ORDERS:
        if o["order_id"].upper() == order_id:
            return o
    return None


def process_return(order_id: str, reason: str):
    """Mark an order as 'Return Requested' and log the reason."""
    order_id = order_id.strip().upper()
    for o in ORDERS:
        if o["order_id"].upper() == order_id:
            if o["status"] != "Delivered":
                return {"success": False,
                        "message": f"Order {order_id} is currently '{o['status']}'. "
                                   f"Only delivered orders can be returned."}
            o["status"] = "Return Requested"
            o["return_reason"] = reason
            return {"success": True,
                    "message": f"Return initiated for order {order_id}. Reason logged: '{reason}'. "
                               f"Refund will be processed in 5-7 business days."}
    return {"success": False, "message": f"Order {order_id} not found."}


def recommend_products(category: str = None, max_price: float = None):
    """Recommend top-rated products, optionally filtered by category/price."""
    filtered = PRODUCTS
    if category:
        filtered = [p for p in filtered if category.lower() in p["category"].lower()]
    if max_price:
        filtered = [p for p in filtered if p["price"] <= max_price]
    filtered = sorted(filtered, key=lambda p: p["rating"], reverse=True)
    return filtered[:3]


TOOL_REGISTRY = {
    "search_product": search_product,
    "check_order_status": check_order_status,
    "process_return": process_return,
    "recommend_products": recommend_products,
}

TOOL_SCHEMAS = [
    {"name": "search_product",
     "description": "Search the product catalog by keyword, name, or category.",
     "input_schema": {"type": "object",
                       "properties": {"query": {"type": "string", "description": "Search keyword, e.g. 'shoes' or 'earbuds'"}},
                       "required": ["query"]}},
    {"name": "check_order_status",
     "description": "Check the current status of a customer's order using the order ID.",
     "input_schema": {"type": "object",
                       "properties": {"order_id": {"type": "string", "description": "Order ID, e.g. ORD1001"}},
                       "required": ["order_id"]}},
    {"name": "process_return",
     "description": "Start a return/refund request for a delivered order.",
     "input_schema": {"type": "object",
                       "properties": {"order_id": {"type": "string", "description": "Order ID, e.g. ORD1001"},
                                      "reason": {"type": "string", "description": "Reason for the return"}},
                       "required": ["order_id", "reason"]}},
    {"name": "recommend_products",
     "description": "Recommend top-rated products, optionally filtered by category and/or max price.",
     "input_schema": {"type": "object",
                       "properties": {"category": {"type": "string", "description": "Product category, e.g. 'Electronics'"},
                                      "max_price": {"type": "number", "description": "Maximum price filter"}},
                       "required": []}},
]


# ======================================================================
# 3. MEMORY  ("Memory" capability -- remembers customer across runs)
# ======================================================================

class AgentMemory:
    def __init__(self):
        self.chat_history = []  # short-term: this conversation only
        self.user_profile = {}  # long-term: persisted to disk
        self._load()

    def _load(self):
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                self.user_profile = json.load(f)
        else:
            self.user_profile = {"name": None, "preferences": [], "past_orders_asked": []}

    def save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.user_profile, f, indent=2)

    def add_message(self, role, content):
        self.chat_history.append({"role": role, "content": content})

    def remember_name(self, name):
        self.user_profile["name"] = name
        self.save()

    def remember_preference(self, pref):
        if pref not in self.user_profile["preferences"]:
            self.user_profile["preferences"].append(pref)
            self.save()

    def remember_order_lookup(self, order_id):
        if order_id not in self.user_profile["past_orders_asked"]:
            self.user_profile["past_orders_asked"].append(order_id)
            self.save()

    def get_context_summary(self):
        parts = []
        if self.user_profile.get("name"):
            parts.append(f"Customer name: {self.user_profile['name']}")
        if self.user_profile.get("preferences"):
            parts.append(f"Known preferences: {', '.join(self.user_profile['preferences'])}")
        if self.user_profile.get("past_orders_asked"):
            parts.append(f"Previously asked about orders: {', '.join(self.user_profile['past_orders_asked'])}")
        return " | ".join(parts) if parts else "No prior info about this customer yet."


# ======================================================================
# 4. LLM MODE  (used automatically if ANTHROPIC_API_KEY is set)
# ======================================================================

USE_LLM = bool(os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an AI E-Commerce Customer Support Agent.
You help customers search products, check order status, process returns, and get recommendations.
Always be polite and concise. Use the available tools whenever the customer's question needs real data
(product info, order status, returns, recommendations) instead of guessing.
Here is what you remember about this customer: {memory_context}
"""

if USE_LLM:
    import anthropic
    client = anthropic.Anthropic()
    MODEL = "claude-sonnet-4-5"


def run_llm_turn(memory: AgentMemory, user_input: str):
    memory.add_message("user", user_input)
    system = SYSTEM_PROMPT.format(memory_context=memory.get_context_summary())
    messages = memory.chat_history.copy()

    response = client.messages.create(model=MODEL, max_tokens=1000, system=system,
                                       tools=TOOL_SCHEMAS, messages=messages)

    while response.stop_reason == "tool_use":
        tool_results = []
        assistant_blocks = []
        for block in response.content:
            if block.type == "text":
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_blocks.append({"type": "tool_use", "id": block.id,
                                          "name": block.name, "input": block.input})
                print(f"   [tool call] {block.name}({block.input})")
                fn = TOOL_REGISTRY[block.name]
                result = fn(**block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                      "content": json.dumps(result, default=str)})

        messages.append({"role": "assistant", "content": assistant_blocks})
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(model=MODEL, max_tokens=1000, system=system,
                                           tools=TOOL_SCHEMAS, messages=messages)

    final_text = "".join(b.text for b in response.content if b.type == "text")
    memory.add_message("assistant", final_text)
    return final_text


# ======================================================================
# 5. RULE-BASED FALLBACK MODE (works offline, no API key needed)
# ======================================================================

def run_rule_based_turn(memory: AgentMemory, user_input: str):
    text = user_input.lower()

    name_match = re.search(r"my name is (\w+)", text)
    if name_match:
        memory.remember_name(name_match.group(1).title())
        return f"Nice to meet you, {name_match.group(1).title()}! How can I help you today?"

    order_match = re.search(r"(ord\d+)", text, re.IGNORECASE)
    if order_match and ("status" in text or "order" in text or "track" in text):
        order_id = order_match.group(1).upper()
        memory.remember_order_lookup(order_id)
        print(f"   [tool call] check_order_status(order_id='{order_id}')")
        order = check_order_status(order_id)
        if order:
            return (f"Order {order['order_id']} ({order['product_name']}) is currently "
                    f"'{order['status']}'. Expected delivery: {order['expected_delivery']}.")
        return f"Sorry, I couldn't find any order with ID {order_id}."

    if "return" in text or "refund" in text:
        if order_match:
            order_id = order_match.group(1).upper()
            reason = "Not specified"
            reason_match = re.search(r"because (.+)", text)
            if reason_match:
                reason = reason_match.group(1)
            print(f"   [tool call] process_return(order_id='{order_id}', reason='{reason}')")
            result = process_return(order_id, reason)
            return result["message"]
        return "Sure, I can help with a return. Could you share your order ID (e.g. ORD1001)?"

    if "recommend" in text or "suggest" in text or "best" in text:
        category = None
        for cat in ["electronics", "footwear", "home", "kitchen", "accessories"]:
            if cat in text:
                category = cat
                break
        print(f"   [tool call] recommend_products(category='{category}')")
        recs = recommend_products(category=category)
        if not recs:
            return "I couldn't find matching recommendations right now."
        lines = [f"- {p['name']} (Rs.{p['price']}, rating {p['rating']})" for p in recs]
        memory.remember_preference(category or "general shopping")
        return "Here are some top picks for you:\n" + "\n".join(lines)

    if "search" in text or "looking for" in text or "find" in text or "product" in text:
        query = text
        for w in ["search", "for", "looking", "find", "product", "products", "i want", "need"]:
            query = query.replace(w, "")
        query = query.strip() or "shoes"
        print(f"   [tool call] search_product(query='{query}')")
        results = search_product(query)
        if not results:
            return f"No products found matching '{query}'."
        lines = [f"- {p['name']} (Rs.{p['price']}) - {p['description']}" for p in results]
        return "Here's what I found:\n" + "\n".join(lines)

    return ("I can help you search products, check an order status, process a return, "
            "or recommend items. Try: 'check status of ORD1001' or 'recommend footwear'.")


# ======================================================================
# 6. MAIN TERMINAL LOOP
# ======================================================================

def main():
    memory = AgentMemory()
    print("=" * 60)
    print(" AI E-COMMERCE CUSTOMER SUPPORT AGENT")
    mode = "Claude LLM + Tool Calling" if USE_LLM else "Rule-based engine (offline demo mode)"
    print(f" Mode: {mode}")
    print(" Type 'exit' to quit.")
    print("=" * 60)
    if memory.user_profile.get("name"):
        print(f"Agent: Welcome back, {memory.user_profile['name']}!")

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Agent: Thank you for shopping with us. Goodbye!")
            break
        if not user_input:
            continue

        reply = run_llm_turn(memory, user_input) if USE_LLM else run_rule_based_turn(memory, user_input)
        print(f"Agent: {reply}")


if __name__ == "__main__":
    main()