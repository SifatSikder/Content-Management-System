"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { CATEGORIES, type Category } from "@/features/projects/constants";

const schema = z.object({
  title: z.string().min(1).max(200),
  category: z.enum(CATEGORIES as unknown as readonly [Category, ...Category[]]),
  description: z.string().optional(),
  due_date: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  onCreated: (p: Project) => void;
  /** The department the new project will be created inside. */
  departmentId: string;
  trigger?: React.ReactNode;
}

export function CreateProjectDialog({ onCreated, departmentId, trigger }: Props) {
  const tProj = useTranslations("projects");
  const tCommon = useTranslations("common");
  const tCat = useTranslations("categories");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const [open, setOpen] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", category: "property_tour", description: "", due_date: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      const project = await createProject({
        title: values.title,
        category: values.category,
        department_id: departmentId,
        description: values.description || null,
        due_date: values.due_date || null,
      });
      onCreated(project);
      toast.success(tToast("project_created"));
      setOpen(false);
      form.reset();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger ?? <Button>{tProj("create")}</Button>}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{tProj("create_title")}</DialogTitle>
          <DialogDescription>{tProj("description_placeholder")}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{tProj("title_label")}</FormLabel>
                  <FormControl>
                    <Input placeholder={tProj("title_placeholder")} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="category"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{tProj("category_label")}</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {tCat(c)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{tProj("description_label")}</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={3}
                      placeholder={tProj("description_placeholder")}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="due_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{tProj("due_date_label")}</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                {tCommon("cancel")}
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {tCommon("save")}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
