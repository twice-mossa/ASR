import { createApp } from "vue";
import { ElButton, ElDialog, ElForm, ElFormItem, ElIcon, ElInput, ElTabPane, ElTabs } from "element-plus";
import "element-plus/es/components/button/style/css";
import "element-plus/es/components/dialog/style/css";
import "element-plus/es/components/form/style/css";
import "element-plus/es/components/form-item/style/css";
import "element-plus/es/components/icon/style/css";
import "element-plus/es/components/input/style/css";
import "element-plus/es/components/tab-pane/style/css";
import "element-plus/es/components/tabs/style/css";
import App from "./App.vue";
import "./styles/theme.css";

const app = createApp(App);

app.component("ElButton", ElButton);
app.component("ElDialog", ElDialog);
app.component("ElForm", ElForm);
app.component("ElFormItem", ElFormItem);
app.component("ElIcon", ElIcon);
app.component("ElInput", ElInput);
app.component("ElTabPane", ElTabPane);
app.component("ElTabs", ElTabs);
app.mount("#app");
