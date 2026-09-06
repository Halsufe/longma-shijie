export const STAGE_LABELS = {
  draft: "筹备中",
  student_apply: "学生填报",
  mentor_select: "导师选择",
  main_pending: "主选待发布",
  main_published: "主选结果已发布",
  supplement_student_apply: "补录填报",
  supplement_mentor_select: "补录导师选择",
  supplement_pending: "补录待发布",
  supplement_blocked: "补录待延长",
  supplement_published: "补录结果已发布",
  completed: "已结束",
  reopened: "已重新开放",
};

export function stageLabel(value) {
  return STAGE_LABELS[value] || value || "未开始";
}

export function roundLabel(value) {
  return value === "supplement" ? "补录" : "主选";
}
