document.addEventListener("DOMContentLoaded", function () {
    // --- DOM 元素選擇 ---
    const itemsContainer = document.getElementById("items-container");
    const addItemButton = document.getElementById("add-item");
    const itemTemplate = document.getElementById("item-template");
    const taxTypeSelect = document.getElementById("tax_type_select");
    const taxCalcMethodDiv = document.getElementById("tax_calculation_method_div");
    const displaySubtotal = document.getElementById("display-subtotal");
    const displayTax = document.getElementById("display-tax");
    const displayTotal = document.getElementById("display-total");

    // --- 核心計算函式 ---
    function calculateAll() {
        let baseAmount = 0;

        // 1. 計算所有明細項目的加總
        document.querySelectorAll(".item-row").forEach((row) => {
            const quantity = parseFloat(row.querySelector(".item-quantity")?.value) || 0;
            const unitPrice = parseFloat(row.querySelector(".item-unit_price")?.value) || 0;
            const subtotal = quantity * unitPrice;
            const subtotalField = row.querySelector(".item-subtotal");
            if (subtotalField) {
                subtotalField.value = "$ " + subtotal.toLocaleString();
            }
            baseAmount += subtotal;
        });

        // 2. 獲取稅務設定
        const taxType = taxTypeSelect.value;
        const taxCalcMethod = document.querySelector('input[name="tax_calculation_method"]:checked')?.value;

        // 3. 根據稅務設定計算最終總額
        let finalSubtotal = 0, finalTax = 0, finalTotal = 0;
        const taxRate = 0.05;

        if (taxType === "TAXABLE") {
            if (taxCalcMethod === "EXCLUSIVE") {
                finalSubtotal = baseAmount;
                finalTax = Math.round(finalSubtotal * taxRate);
            } else if (taxCalcMethod === "INCLUSIVE") {
                finalTotal = baseAmount;
                finalSubtotal = Math.round(finalTotal / (1 + taxRate));
                finalTax = finalTotal - finalSubtotal;
            } else {
                // 如果沒有選擇計稅方式，或選擇了其他選項，預設為未稅
                finalSubtotal = baseAmount;
            }
        } else { // 免稅或零稅率
            finalSubtotal = baseAmount;
        }
        finalTotal = finalSubtotal + finalTax;

        // 4. 更新頁面下方的總金額顯示
        if (displaySubtotal) displaySubtotal.textContent = "$ " + finalSubtotal.toLocaleString();
        if (displayTax) displayTax.textContent = "$ " + finalTax.toLocaleString();
        if (displayTotal) displayTotal.textContent = "$ " + finalTotal.toLocaleString();
    }

    // --- UI互動函式 ---

    // 根據稅別選擇，顯示或隱藏計稅方式
    function toggleTaxCalculationMethod() {
        if (taxCalcMethodDiv) {
            taxCalcMethodDiv.style.display = taxTypeSelect.value === "TAXABLE" ? "block" : "none";
        }
        calculateAll();
    }

    // 新增一個空白的明細項目
    function addNewItem() {
        if (!itemTemplate || !itemsContainer) return;
        let index = itemsContainer.querySelectorAll(".item-row").length;
        let newRowHtml = itemTemplate.innerHTML.replace(/__prefix__/g, index);

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = newRowHtml;
        const newRow = tempDiv.firstElementChild; // 取得 row DOM 元素

        itemsContainer.appendChild(newRow);

        // 複製第一個費用分類的選項到新的下拉選單
        const firstCategorySelect = document.querySelector(".item-category");
        const newCategorySelect = newRow.querySelector(".item-category");
        if (firstCategorySelect && newCategorySelect) {
            newCategorySelect.innerHTML = firstCategorySelect.innerHTML;
        }

        // 為新項目中的輸入框加上事件監聽
        addInputListeners(newRow);
    }

    // 重新整理所有項目的索引 (name 屬性中的數字)
    function updateIndices() {
        itemsContainer.querySelectorAll(".item-row").forEach((row, index) => {
            row.querySelectorAll("input, select").forEach((input) => {
                if (input.name) {
                    input.name = input.name.replace(/items-\d+-/, "items-" + index + "-");
                    input.id = input.id.replace(/items-\d+-/, "items-" + index + "-");
                }
                // 同步更新 label 的 for 屬性
                const label = row.querySelector(`label[for^="items-${index}-"]`);
                if (label && input.id) {
                    label.setAttribute('for', input.id);
                }
            });
        });
    }

    // 為指定的 DOM 元素內的輸入框加上事件監聽
    function addInputListeners(element) {
        // 監聽數量或單價的變動
        element.addEventListener("input", (e) => {
            if (
                e.target.classList.contains("item-quantity") ||
                e.target.classList.contains("item-unit_price")
            ) {
                calculateAll();
            }
        });

        // 監聽移除按鈕的點擊
        element.addEventListener("click", (e) => {
            const removeButton = e.target.closest(".remove-item");
            if (removeButton) {
                removeButton.closest(".item-row").remove();
                updateIndices();
                calculateAll();
            }
        });
    }


    // --- 初始化與事件綁定 ---

    // 頁面載入時，為現有的項目加上事件監聽 (主要用於編輯頁面)
    addInputListeners(itemsContainer);

    // 綁定 "新增明細" 按鈕
    if (addItemButton) {
        addItemButton.addEventListener("click", addNewItem);
    }

    // 綁定稅別下拉選單
    if (taxTypeSelect) {
        taxTypeSelect.addEventListener("change", toggleTaxCalculationMethod);
    }

    // 綁定計稅方式選項
    document.querySelectorAll('input[name="tax_calculation_method"]').forEach((radio) =>
        radio.addEventListener("change", calculateAll)
    );

    // --- 首次執行 ---

    // 頁面載入時先執行一次，以確保編輯頁面的初始值正確
    toggleTaxCalculationMethod();

    // 如果是新增頁面 (itemsContainer 內是空的)，則自動新增一筆空白明細
    if (itemsContainer && itemsContainer.children.length === 0) {
        addNewItem();
    }
});