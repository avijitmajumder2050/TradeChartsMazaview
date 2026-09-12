(function () {
  "use strict";

  var listEl = document.getElementById("scannerList");
  var options = Array.prototype.slice.call(
    listEl.querySelectorAll(".scanner-option")
  );
  var runBtn = document.getElementById("runBtn");
  var statusEl = document.getElementById("status");
  var statsEl = document.getElementById("stats");
  var tableWrap = document.getElementById("tableWrap");
  var metaEl = document.getElementById("meta");
  var descEl = document.getElementById("scannerDesc");

  var selectedId = window.INITIAL_SCANNER_ID || "";

  function getSelectedOption() {
    return options.filter(function (o) {
      return o.getAttribute("data-id") === selectedId;
    })[0];
  }

  function describeScanner() {
    var opt = getSelectedOption();
    descEl.textContent = opt ? opt.getAttribute("data-description") || "" : "";
  }

  function selectScanner(id) {
    selectedId = id;
    options.forEach(function (o) {
      o.classList.toggle("selected", o.getAttribute("data-id") === id);
    });
    describeScanner();
    runScanner();
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderStats(stats) {
    statsEl.innerHTML = (stats || [])
      .map(function (s) {
        return (
          '<div class="stat">' +
          '<div class="value">' + escapeHtml(s.value) + "</div>" +
          '<div class="label">' + escapeHtml(s.label) + "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  function isNumericType(type) {
    return type === "num" || type === "pct";
  }

  function formatCell(col, row) {
    var value = row[col.key];

    if (value === null || value === undefined || value === "") {
      return '<span class="dim">-</span>';
    }

    if (col.type === "bool") {
      return value
        ? '<span class="badge">YES</span>'
        : '<span class="dim">No</span>';
    }

    if (col.type === "pct") {
      var num = Number(value);
      if (!Number.isFinite(num)) return escapeHtml(value);
      var cls = num >= 0 ? "up" : "down";
      var sign = num >= 0 ? "+" : "";
      return '<span class="' + cls + '">' + sign + num.toFixed(2) + "%</span>";
    }

    if (col.type === "num") {
      var n = Number(value);
      return Number.isFinite(n) ? '<span class="num">' + n.toLocaleString("en-IN") + "</span>" : escapeHtml(value);
    }

    return escapeHtml(value);
  }

  function renderTable(columns, rows) {
    if (!rows || !rows.length) {
      tableWrap.innerHTML = '<div class="empty">No matches</div>';
      return;
    }

    var thead = columns
      .map(function (c) {
        return (
          '<th class="' + (isNumericType(c.type) ? "num" : "") + '">' +
          escapeHtml(c.label) +
          "</th>"
        );
      })
      .join("");

    var tbody = rows
      .map(function (row) {
        var cells = columns
          .map(function (c) {
            return (
              '<td class="' + (isNumericType(c.type) ? "num" : "") + '">' +
              formatCell(c, row) +
              "</td>"
            );
          })
          .join("");
        return "<tr>" + cells + "</tr>";
      })
      .join("");

    tableWrap.innerHTML =
      '<div class="table-wrap"><table><thead><tr>' +
      thead +
      "</tr></thead><tbody>" +
      tbody +
      "</tbody></table></div>";
  }

  function setStatus(text, mode) {
    statusEl.textContent = text || "";
    statusEl.className = "status" + (mode ? " " + mode : "");
  }

  function runScanner() {
    var id = selectedId;

    if (!id) {
      setStatus("", "");
      statsEl.innerHTML = "";
      tableWrap.innerHTML = "";
      metaEl.textContent = "";
      return;
    }

    runBtn.disabled = true;
    setStatus(
      "Running scanner on the backend — this calls Chartink live, it can take a few seconds…",
      "loading"
    );
    statsEl.innerHTML = "";
    tableWrap.innerHTML = "";
    metaEl.textContent = "";

    fetch("/api/scanners/" + encodeURIComponent(id) + "/run")
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        var data = result.data;

        if (!result.ok || data.error) {
          setStatus("Error: " + (data.error || "Unknown error"), "error");
          return;
        }

        setStatus("", "");
        renderStats(data.stats);
        renderTable(data.columns, data.rows);
        metaEl.textContent = "Generated " + data.generated_at;
      })
      .catch(function (err) {
        setStatus("Request failed: " + err.message, "error");
      })
      .finally(function () {
        runBtn.disabled = false;
      });
  }

  options.forEach(function (opt) {
    opt.addEventListener("click", function () {
      selectScanner(opt.getAttribute("data-id"));
    });
  });

  runBtn.addEventListener("click", runScanner);

  describeScanner();

  if (selectedId) {
    runScanner();
  }
})();
