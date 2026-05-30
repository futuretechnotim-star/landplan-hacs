/**
 * Tests for SmartFarmViewSnapshotCard custom element.
 * jsdom provides the DOM; we register the element manually before each test.
 */

const cardSrc = require("fs").readFileSync(
  require("path").join(
    __dirname,
    "../../custom_components/landplan/www/smartfarmview-snapshot-card.js"
  ),
  "utf8"
);

// jsdom provides real customElements — eval the card to register it, then retrieve via .get()
eval(cardSrc); // eslint-disable-line no-eval

const CardClass = customElements.get("smartfarmview-snapshot-card");

function makeCard(config = {}) {
  const card = new CardClass();
  card.setConfig({
    camera_entity: "camera.node1",
    button_entity: "button.node1_capture",
    ...config,
  });
  return card;
}

function makeHass(entityAttrs = {}) {
  const defaults = {
    access_token: "tok123",
    ...entityAttrs,
  };
  return {
    states: {
      "camera.node1": {
        attributes: defaults,
        last_updated: new Date(Date.now() - 5 * 60_000).toISOString(),
      },
    },
    callService: jest.fn().mockResolvedValue(undefined),
  };
}

describe("setConfig", () => {
  test("throws if camera_entity is missing", () => {
    const card = new CardClass();
    expect(() => card.setConfig({ button_entity: "button.x" })).toThrow("camera_entity");
  });

  test("throws if button_entity is missing", () => {
    const card = new CardClass();
    expect(() => card.setConfig({ camera_entity: "camera.x" })).toThrow("button_entity");
  });

  test("renders shadow DOM on first setConfig", () => {
    const card = makeCard();
    expect(card.shadowRoot.getElementById("image-wrap")).not.toBeNull();
    expect(card.shadowRoot.getElementById("capture-btn")).not.toBeNull();
  });

  test("does not re-render on second setConfig call", () => {
    const card = makeCard();
    const wrap = card.shadowRoot.getElementById("image-wrap");
    card.setConfig({ camera_entity: "camera.node1", button_entity: "button.node1_capture" });
    expect(card.shadowRoot.getElementById("image-wrap")).toBe(wrap);
  });
});

describe("image rendering", () => {
  test("shows placeholder when hass has no access_token", () => {
    const card = makeCard();
    card.hass = makeHass({ access_token: undefined });
    const placeholder = card.shadowRoot.getElementById("placeholder");
    expect(placeholder.style.display).not.toBe("none");
  });

  test("renders img element when access_token is present", () => {
    const card = makeCard();
    card.hass = makeHass();
    const img = card.shadowRoot.querySelector("img");
    expect(img).not.toBeNull();
    expect(img.src).toContain("/api/camera_proxy/camera.node1");
    expect(img.src).toContain("tok123");
  });

  test("cache-busts src using entity last_updated", () => {
    const card = makeCard();
    const hass = makeHass();
    card.hass = hass;
    const img = card.shadowRoot.querySelector("img");
    const expected = String(new Date(hass.states["camera.node1"].last_updated).getTime());
    expect(img.src).toContain(`_t=${expected}`);
  });

  test("does not re-set img src if last_updated has not changed", () => {
    const fixedTime = "2024-01-01T12:00:00.000Z";
    const card = makeCard();
    const hass = makeHass();
    hass.states["camera.node1"].last_updated = fixedTime;
    card.hass = hass;
    const firstSrc = card.shadowRoot.querySelector("img").src;
    hass.states["camera.node1"].last_updated = fixedTime; // unchanged
    card.hass = hass;
    expect(card.shadowRoot.querySelector("img").src).toBe(firstSrc);
  });
});

describe("age display", () => {
  test("shows 'captured just now' for sub-minute age", () => {
    const card = makeCard();
    const hass = makeHass();
    hass.states["camera.node1"].last_updated = new Date(Date.now() - 10_000).toISOString();
    card.hass = hass;
    expect(card.shadowRoot.getElementById("age").textContent).toBe("captured just now");
  });

  test("shows singular minute", () => {
    const card = makeCard();
    const hass = makeHass();
    hass.states["camera.node1"].last_updated = new Date(Date.now() - 75_000).toISOString();
    card.hass = hass;
    expect(card.shadowRoot.getElementById("age").textContent).toBe("captured 1 minute ago");
  });

  test("shows plural minutes", () => {
    const card = makeCard();
    const hass = makeHass();
    hass.states["camera.node1"].last_updated = new Date(Date.now() - 5 * 60_000).toISOString();
    card.hass = hass;
    expect(card.shadowRoot.getElementById("age").textContent).toBe("captured 5 minutes ago");
  });

  test("shows dash when entity is absent", () => {
    const card = makeCard();
    card.hass = { states: {}, callService: jest.fn() };
    expect(card.shadowRoot.getElementById("age").textContent).toBe("–");
  });
});

describe("capture button", () => {
  test("calls button.press service on click", async () => {
    const card = makeCard();
    const hass = makeHass();
    card.hass = hass;
    card.shadowRoot.getElementById("capture-btn").click();
    await Promise.resolve(); // flush microtask
    expect(hass.callService).toHaveBeenCalledWith("button", "press", {
      entity_id: "button.node1_capture",
    });
  });

  test("disables button during capture", async () => {
    const card = makeCard();
    card.hass = makeHass();
    const btn = card.shadowRoot.getElementById("capture-btn");
    btn.click();
    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toBe("Capturing…");
  });

  test("getCardSize returns 4", () => {
    expect(makeCard().getCardSize()).toBe(4);
  });
});
