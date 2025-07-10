document.addEventListener("DOMContentLoaded", function () {
    // --- DOM 元素選擇 ---
    const form = document.getElementById("expenditure-form");
    const itemsContainer = document.getElementById("items-container");
    const addItemButton = document.getElementById("add-item");
    const itemTemplate = document.getElementById("item-template");
    const taxTypeSelect = document.getElementById("tax_type_select");
    const displaySubtotal = document.getElementById("display-subtotal");
    const displayTax = document.getElementById("display-tax");
    const displayTotal = document.getElementById("display-total");

    // --- 核心計算函式 (已修正) ---
    function calculateAll() {
        let baseAmount = 0;

        // 1. 遍歷所有明細列
        itemsContainer.querySelectorAll(".item-row").forEach((row) => {
            const quantity = parseFloat(row.querySelector(".item-quantity")?.value) || 0;
            const unitPrice = parseFloat(row.querySelector(".item-unit_price")?.value) || 0;
            const lineTotal = quantity * unitPrice;

            // --- ✨ 新增：更新每一行的小計欄位 ---
            const lineTotalInput = row.querySelector(".item-line-total");
            if (lineTotalInput) {
                lineTotalInput.value = '$ ' + lineTotal.toLocaleString();
            }

            baseAmount += lineTotal;
        });

        // 2. 根據稅務設定計算最終總額
        const taxType = taxTypeSelect ? taxTypeSelect.value : 'TAX_EXEMPT';
        const taxCalcMethod = document.querySelector('input[name="tax_calculation_method"]:checked')?.value;
        let finalSubtotal = 0, finalTax = 0, finalTotal = 0;
        const taxRate = 0.05;

        if (taxType === "TAXABLE") {
            if (taxCalcMethod === "INCLUSIVE") {
                finalTotal = baseAmount;
                finalSubtotal = Math.round(finalTotal / (1 + taxRate));
                finalTax = finalTotal - finalSubtotal;
            } else { // 預設為稅外加 (EXCLUSIVE)
                finalSubtotal = baseAmount;
                // --- ✨ 修正錯字：base_amount -> baseAmount ---
                finalTax = Math.round(finalSubtotal * taxRate);
            }
        } else {
            finalSubtotal = baseAmount;
        }
        finalTotal = finalSubtotal + finalTax;

        // 3. 更新頁面下方的總金額顯示
        if (displaySubtotal) displaySubtotal.textContent = "$ " + finalSubtotal.toLocaleString();
        if (displayTax) displayTax.textContent = "$ " + finalTax.toLocaleString();
        if (displayTotal) displayTotal.textContent = "$ " + finalTotal.toLocaleString();
    }

    // --- 事件處理函式 ---
    function addNewItem() {
        if (!itemTemplate) return;
        let index = itemsContainer.children.length;
        let newRowHtml = itemTemplate.innerHTML.replace(/__prefix__/g, index);
        itemsContainer.insertAdjacentHTML("beforeend", newRowHtml);
    }

    // --- 事件綁定 ---
    // 使用事件代理，一次性處理所有明細的新增、刪除與輸入
    form.addEventListener('input', (e) => {
        if (e.target.matches('.item-quantity, .item-unit_price')) {
            calculateAll();
        }
    });

    form.addEventListener('click', (e) => {
        if (e.target.closest('#add-item')) {
            e.preventDefault(); // 防止按鈕觸發任何表單預設行為
            addNewItem();
        }
        if (e.target.closest('.remove-item')) {
            e.preventDefault();
            e.target.closest('.item-row').remove();
            calculateAll(); // 刪除後要重新計算
        }
    });

    // 綁定稅務選項的變動
    if (taxTypeSelect) {
        taxTypeSelect.addEventListener('change', calculateAll);
    }
    document.querySelectorAll('input[name="tax_calculation_method"]').forEach(radio => {
        radio.addEventListener('change', calculateAll);
    });

    // --- 初始化 ---
    // 如果是新增頁面，自動新增第一筆空白明細
    if (itemsContainer && itemsContainer.children.length === 0) {
        addNewItem();
    }
    // 頁面載入時，先執行一次完整計算
    calculateAll();
});