/* advanced_shell.c
 * Advanced custom shell for Ubuntu / Linux
 * Features:
 *  - Prompt with username@hostname:cwd
 *  - Built-ins: cd, exit, help, history, jobs, fg, bg
 *  - Command parsing with arguments
 *  - Pipelines (|)
 *  - I/O redirection (<, >, >>)
 *  - Background execution (&)
 *  - Job control (track background jobs, bring to foreground)
 *  - Signal handling (SIGINT, SIGTSTP, SIGCHLD)
 *  - Persistent history (~/.adv_shell_history)
 *
 * Compile:
 *   gcc shell.c -o advsh -std=gnu11 -Wall
 * Run:
 *   ./advsh
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <pwd.h>
#include <fcntl.h>
#include <signal.h>
#include <errno.h>
#include <limits.h>
#include <linux/limits.h>
#include <ctype.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#define MAX_LINE 4096
#define MAX_TOKENS 256
#define MAX_JOBS 1024
#define HISTORY_FILE ".adv_shell_history"
#define HISTORY_LIMIT 1000

typedef enum { RUNNING, STOPPED, DONE } job_state_t;

typedef struct job {
    int id;
    pid_t pgid; // process group id
    char *cmdline;
    job_state_t state;
} job_t;

static job_t jobs[MAX_JOBS];
static int next_job_id = 1;

// History
static char *history[HISTORY_LIMIT];
static int history_count = 0;

// Foreground process group
static pid_t shell_pgid;
static int shell_terminal;

// Forward declarations
void load_history();
void save_history();
void add_history(const char *line);
void print_history();

// Job control
int add_job(pid_t pgid, const char *cmdline, job_state_t state);
job_t* find_job_by_id(int id);
job_t* find_job_by_pgid(pid_t pgid);
void remove_done_jobs();
void print_jobs();
void wait_for_job(job_t *j);

// Parsing & execution
char *read_line();
char **split_tokens(char *line, int *ntokens);
void free_tokens(char **tokens);
int is_builtin(char **args);
int run_builtin(char **args);
int launch_pipeline(char ***commands, int ncmds, int background, const char *full_cmdline);
int parse_and_execute(char *line);

// Signal handlers
void sigint_handler(int signo);
void sigtstp_handler(int signo);
void sigchld_handler(int signo);

// Utilities
char *trim_whitespace(char *str);
char *strdup_safe(const char *s);

int main() {
    // CRITICAL: Disable output buffering to ensure GUI receives output immediately via pipe
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    // Check if we are running interactively
    shell_terminal = STDIN_FILENO;
    int interactive = isatty(shell_terminal);

    if (interactive) {
        while (tcgetpgrp(shell_terminal) != (shell_pgid = getpgrp()))
            kill(-shell_pgid, SIGTTIN);
        
        // Put shell in its own process group
        shell_pgid = getpid();
        if (setpgid(shell_pgid, shell_pgid) < 0) {
            perror("setpgid");
        }
        tcsetpgrp(shell_terminal, shell_pgid);
    } else {
        shell_pgid = getpid();
    }

    // Install signal handlers
    struct sigaction sa;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;

    sa.sa_handler = sigint_handler;
    sigaction(SIGINT, &sa, NULL);

    sa.sa_handler = sigtstp_handler;
    sigaction(SIGTSTP, &sa, NULL);

    sa.sa_handler = sigchld_handler;
    sa.sa_flags = SA_RESTART | SA_NOCLDSTOP;
    sigaction(SIGCHLD, &sa, NULL);
    
    // Ignore SIGTTOU/SIGTTIN to avoid stopping shell when handing over terminal
    signal(SIGTTOU, SIG_IGN);
    signal(SIGTTIN, SIG_IGN);

    load_history();

    while (1) {
        // Print prompt: user@host:cwd$
        // Always print prompt even if non-interactive, as GUI expects it? 
        // Actually, normally shells don't print prompt in script mode. 
        // But for GUI wrapper, we might want it. However, GUI doesn't parse prompt.
        // We will print it for visual feedback if interactive or force enable.
        
        char cwd[PATH_MAX];
        if (getcwd(cwd, sizeof(cwd)) == NULL) strncpy(cwd, "?", sizeof(cwd));
        struct passwd *pw = getpwuid(getuid());
        char hostname[256];
        if (gethostname(hostname, sizeof(hostname)) != 0) strncpy(hostname, "host", sizeof(hostname));
        
        // Check for home dir replacement
        const char *home = getenv("HOME");
        if (home && strncmp(cwd, home, strlen(home)) == 0) {
             printf("%s@%s:~%s$ ", pw ? pw->pw_name : "user", hostname, cwd + strlen(home));
        } else {
             printf("%s@%s:%s$ ", pw ? pw->pw_name : "user", hostname, cwd);
        }
        
        // read_line handles input
        char *line = read_line();
        if (!line) {
            // EOF (Ctrl-D)
            break; 
        }
        char *trimmed = trim_whitespace(line);
        if (strlen(trimmed) == 0) { free(line); continue; }

        add_history(trimmed);

        parse_and_execute(trimmed);
        
        free(line);
        remove_done_jobs();
    }

    save_history();
    return 0;
}

/* -------------------- History -------------------- */
void load_history() {
    char path[PATH_MAX];
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    snprintf(path, sizeof(path), "%s/%s", home, HISTORY_FILE);
    FILE *f = fopen(path, "r");
    if (!f) return;
    char *line = NULL;
    size_t n = 0;
    while (getline(&line, &n, f) != -1) {
        line[strcspn(line, "\n")] = 0;
        if (history_count < HISTORY_LIMIT)
            history[history_count++] = strdup_safe(line);
    }
    free(line);
    fclose(f);
}

void save_history() {
    char path[PATH_MAX];
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    snprintf(path, sizeof(path), "%s/%s", home, HISTORY_FILE);
    FILE *f = fopen(path, "w");
    if (!f) return;
    int start = history_count > HISTORY_LIMIT ? history_count - HISTORY_LIMIT : 0;
    for (int i = start; i < history_count; ++i) {
        fprintf(f, "%s\n", history[i]);
    }
    fclose(f);
}

void add_history(const char *line) {
    if (history_count >= HISTORY_LIMIT) {
        free(history[0]);
        memmove(&history[0], &history[1], sizeof(char*) * (HISTORY_LIMIT-1));
        history_count = HISTORY_LIMIT - 1;
    }
    history[history_count++] = strdup_safe(line);
}

void print_history() {
    for (int i = 0; i < history_count; ++i) {
        printf("%4d  %s\n", i+1, history[i]);
    }
}

/* -------------------- Job control -------------------- */
int add_job(pid_t pgid, const char *cmdline, job_state_t state) {
    for (int i = 0; i < MAX_JOBS; ++i) {
        if (jobs[i].id == 0) {
            jobs[i].id = next_job_id++;
            jobs[i].pgid = pgid;
            jobs[i].cmdline = strdup_safe(cmdline ? cmdline : "");
            jobs[i].state = state;
            return jobs[i].id;
        }
    }
    fprintf(stderr, "job list full\n");
    return -1;
}

job_t* find_job_by_id(int id) {
    for (int i = 0; i < MAX_JOBS; ++i) if (jobs[i].id == id) return &jobs[i];
    return NULL;
}

job_t* find_job_by_pgid(pid_t pgid) {
    for (int i = 0; i < MAX_JOBS; ++i) if (jobs[i].pgid == pgid && jobs[i].id != 0) return &jobs[i];
    return NULL;
}

void remove_job_at_index(int idx) {
    if (jobs[idx].id != 0) {
        free(jobs[idx].cmdline);
        jobs[idx].id = 0;
        jobs[idx].pgid = 0;
        jobs[idx].state = DONE;
    }
}

void remove_done_jobs() {
    for (int i = 0; i < MAX_JOBS; ++i) {
        if (jobs[i].id != 0 && jobs[i].state == DONE) {
            remove_job_at_index(i);
        }
    }
}

void print_jobs() {
    for (int i = 0; i < MAX_JOBS; ++i) {
        if (jobs[i].id != 0) {
            const char *s = jobs[i].state == RUNNING ? "Running" : jobs[i].state == STOPPED ? "Stopped" : "Done";
            printf("[%d] %s\t%s\n", jobs[i].id, s, jobs[i].cmdline);
        }
    }
}

void wait_for_job(job_t *j) {
    int status;
    while (j->state == RUNNING) {
        pid_t pid = waitpid(-j->pgid, &status, WUNTRACED);
        if (pid < 0) {
             if (errno == ECHILD) {
                 // Job gone
                 j->state = DONE;
                 break;
             }
             perror("waitpid");
             break;
        }
        
        if (WIFSTOPPED(status)) {
            j->state = STOPPED;
            printf("\n[%d] Stopped %s\n", j->id, j->cmdline);
        } else if (WIFEXITED(status) || WIFSIGNALED(status)) {
            j->state = DONE;
        }
    }
}

/* -------------------- Parsing & Execution -------------------- */

// Read a full line (supports long lines)
char *read_line() {
    char *line = NULL;
    size_t size = 0;
    
    // Clear errno before call
    errno = 0;
    ssize_t nread = getline(&line, &size, stdin);
    
    if (nread == -1) {
        if (errno != 0) {
            // Real error
            perror("getline");
        }
        free(line);
        return NULL;
    }
    return line;
}

char *strdup_safe(const char *s) {
    if (!s) return NULL;
    char *res = strdup(s);
    if (!res) {
        perror("strdup");
        exit(1);
    }
    return res;
}

char *trim_whitespace(char *str) {
    while (*str && isspace((unsigned char)*str)) ++str;
    if (*str == 0) return str;
    char *end = str + strlen(str) - 1;
    while (end > str && isspace((unsigned char)*end)) *end-- = 0;
    return str;
}

char **split_tokens(char *line, int *ntokens) {
    int capacity = 16;
    char **tokens = malloc(capacity * sizeof(char*));
    *ntokens = 0;
    
    char *p = line;
    while (*p) {
        while (*p && isspace((unsigned char)*p)) p++; // skip whitespace
        if (!*p) break;
        
        if (*ntokens >= capacity - 1) {
            capacity *= 2;
            tokens = realloc(tokens, capacity * sizeof(char*));
        }

        // Handle quotes
        if (*p == '"' || *p == '\'') {
            char quote = *p++;
            char *start = p;
            while (*p) {
                if (*p == '\\' && *(p+1)) {
                    p += 2; // Skip escaped char
                    continue;
                }
                if (*p == quote) break;
                p++;
            }
            if (*p == quote) *p++ = 0;
            tokens[(*ntokens)++] = strdup_safe(start);
        } else {
            char *start = p;
            while (*p && !isspace((unsigned char)*p) && *p != '<' && *p != '>' && *p != '|') p++;
            
            // Handle special chars being stuck to words, e.g. ls|grep or ls>out
            if (p == start) {
                // We stopped at a special char immediately
                // If it's redirection/pipe, make it a token
                if (*p == '<' || *p == '>' || *p == '|') {
                    char tmp[3] = { *p, 0, 0 };
                    if (*p == '>' && *(p+1) == '>') {
                        tmp[1] = '>';
                        p++;
                    }
                    tokens[(*ntokens)++] = strdup_safe(tmp);
                    p++;
                } else {
                    p++; // Should not happen with isspace check, just safety
                }
            } else {
                 // We have a word
                 char saved = *p;
                 *p = 0;
                 tokens[(*ntokens)++] = strdup_safe(start);
                 *p = saved; // restore for next check
                 // DO NOT increment p here, let the next loop handle the special char
            }
        }
    }
    tokens[*ntokens] = NULL;
    return tokens;
}

void free_tokens(char **tokens) {
    if (!tokens) return;
    for (int i = 0; tokens[i]; ++i) free(tokens[i]);
    free(tokens);
}

int is_builtin(char **args) {
    if (!args[0]) return 0;
    if (strcmp(args[0], "cd") == 0) return 1;
    if (strcmp(args[0], "exit") == 0) return 1;
    if (strcmp(args[0], "help") == 0) return 1;
    if (strcmp(args[0], "history") == 0) return 1;
    if (strcmp(args[0], "jobs") == 0) return 1;
    if (strcmp(args[0], "fg") == 0) return 1;
    if (strcmp(args[0], "bg") == 0) return 1;
    return 0;
}

int run_builtin(char **args) {
    if (strcmp(args[0], "cd") == 0) {
        if (!args[1]) {
            chdir(getenv("HOME"));
        } else {
            if (chdir(args[1]) != 0) {
                perror("cd");
            }
        }
        return 1;
    }
    if (strcmp(args[0], "exit") == 0) {
        exit(0);
    }
    if (strcmp(args[0], "help") == 0) {
        printf("Advanced Custom Shell\nBuilt-ins: cd, exit, history, jobs, fg, bg\n");
        return 1;
    }
    if (strcmp(args[0], "history") == 0) {
        print_history();
        return 1;
    }
    if (strcmp(args[0], "jobs") == 0) {
        print_jobs();
        return 1;
    }
    if (strcmp(args[0], "fg") == 0) {
        if (!args[1]) {
             fprintf(stderr, "fg: usage: fg <job_id>\n");
             return 1;
        }
        int id = atoi(args[1]);
        job_t *j = find_job_by_id(id);
        if (!j) { fprintf(stderr, "fg: no such job\n"); return 1; }
        
        if (tcsetpgrp(shell_terminal, j->pgid) < 0) {
            // perror("tcsetpgrp"); 
            // Ignored if not TTY
        }
        
        // Continue if stopped
        if (j->state == STOPPED) {
            kill(-j->pgid, SIGCONT);
            j->state = RUNNING;
        }
        
        wait_for_job(j);
        
        tcsetpgrp(shell_terminal, shell_pgid);
        return 1;
    }
    if (strcmp(args[0], "bg") == 0) {
         if (!args[1]) {
             fprintf(stderr, "bg: usage: bg <job_id>\n");
             return 1;
        }
        int id = atoi(args[1]);
        job_t *j = find_job_by_id(id);
        if (!j) { fprintf(stderr, "bg: no such job\n"); return 1; }
        
        if (j->state == STOPPED) {
            kill(-j->pgid, SIGCONT);
            j->state = RUNNING;
            printf("[%d] %s &\n", j->id, j->cmdline);
        }
        return 1;
    }
    return 0;
}

int launch_pipeline(char ***commands, int ncmds, int background, const char *full_cmdline) {
    int pipefd[2 * (ncmds - 1)];
    pid_t pids[ncmds];
    
    // Create pipes
    for (int i = 0; i < ncmds - 1; ++i) {
        if (pipe(pipefd + i * 2) < 0) {
            perror("pipe");
            return -1;
        }
    }
    
    pid_t pgid = 0;
    
    for (int i = 0; i < ncmds; ++i) {
        pids[i] = fork();
        
        if (pids[i] < 0) {
            perror("fork");
            return -1;
        } else if (pids[i] == 0) {
            // Child
            
            // Set PGID
            pid_t pid = getpid();
            if (pgid == 0) pgid = pid;
            setpgid(pid, pgid);
            if (!background && i == 0) { // Only first time? No, tcsetpgrp takes pgid
                 // We don't need to do it here, parent does it.
            }
            
            // Handle Signals (Default)
            signal(SIGINT, SIG_DFL);
            signal(SIGTSTP, SIG_DFL);
            signal(SIGCHLD, SIG_DFL);
            signal(SIGTTOU, SIG_DFL);
            signal(SIGTTIN, SIG_DFL);
            
            // Pipes
            if (i > 0) {
                dup2(pipefd[(i - 1) * 2], STDIN_FILENO);
            }
            if (i < ncmds - 1) {
                dup2(pipefd[i * 2 + 1], STDOUT_FILENO);
            }
            
            // Close all pipe fds
            for (int k = 0; k < 2 * (ncmds - 1); ++k) close(pipefd[k]);
            
            // Parse arguments for redirection
            char **cmd = commands[i];
            // Since we need to modify args for redirection, we build a new argv
            // Simplification: we'll just scan tokens in split_tokens properly, 
            // but we passed an array. We need to construct new argv without < > items
            
            char *new_argv[MAX_TOKENS];
            int argc_new = 0;
            
            for (int j = 0; cmd[j] != NULL; ) {
                if (strcmp(cmd[j], "<") == 0) {
                    if (cmd[j+1]) {
                        int fd = open(cmd[j+1], O_RDONLY);
                        if (fd < 0) { perror(cmd[j+1]); exit(1); }
                        dup2(fd, STDIN_FILENO);
                        close(fd);
                        j += 2;
                    } else {
                         fprintf(stderr, "Syntax error: expected file after <\n");
                         exit(1);
                    }
                } else if (strcmp(cmd[j], ">") == 0) {
                    if (cmd[j+1]) {
                        int fd = open(cmd[j+1], O_WRONLY | O_CREAT | O_TRUNC, 0644);
                        if (fd < 0) { perror(cmd[j+1]); exit(1); }
                        dup2(fd, STDOUT_FILENO);
                        close(fd);
                        j += 2;
                    } else {
                         fprintf(stderr, "Syntax error: expected file after >\n");
                         exit(1);
                    }
                } else if (strcmp(cmd[j], ">>") == 0) {
                     if (cmd[j+1]) {
                        int fd = open(cmd[j+1], O_WRONLY | O_CREAT | O_APPEND, 0644);
                        if (fd < 0) { perror(cmd[j+1]); exit(1); }
                        dup2(fd, STDOUT_FILENO);
                        close(fd);
                        j += 2;
                    } else {
                         fprintf(stderr, "Syntax error: expected file after >>\n");
                         exit(1);
                    }
                } else {
                    new_argv[argc_new++] = cmd[j++];
                }
            }
            new_argv[argc_new] = NULL;
            
            execvp(new_argv[0], new_argv);
            perror(new_argv[0]);
            exit(1);
        } else {
            // Parent
            if (pgid == 0) pgid = pids[i]; // First child sets PGID
            setpgid(pids[i], pgid);
        }
    }
    
    // Close parent pipes
    for (int i = 0; i < 2 * (ncmds - 1); ++i) close(pipefd[i]);
    
    if (background) {
        add_job(pgid, full_cmdline, RUNNING);
        printf("[%d] %d\n", next_job_id-1, pgid);
    } else {
        // Wait for all in pgid
        tcsetpgrp(shell_terminal, pgid);
        
        // Wait for the lead process roughly, or use job control wait
        // Simplified: wait for last process, but proper shell waits for all
        // We will add to job list as foreground job, then wait
        int job_id = add_job(pgid, full_cmdline, RUNNING);
        job_t *node = find_job_by_id(job_id);
        wait_for_job(node);
        
        tcsetpgrp(shell_terminal, shell_pgid);
    }

    return 0;
}

int parse_and_execute(char *line) {
    if (!line || !*line) return 0;
    
    int ntokens;
    char **tokens = split_tokens(line, &ntokens);
    if (ntokens == 0) { free(tokens); return 0; }
    
    // Check for background &
    int background = 0;
    if (strcmp(tokens[ntokens-1], "&") == 0) {
        background = 1;
        free(tokens[ntokens-1]);
        tokens[ntokens-1] = NULL;
        ntokens--;
        if (ntokens == 0) { free(tokens); return 0; }
    }
    
    // Check builtin
    if (is_builtin(tokens) && !background && ntokens > 0) {
        // Builtins run in shell process (cannot pipe builtins in this simple shell)
        // If piping led here, we'd need more logic. 
        // For simplicity, builtins are standalone.
        int ret = run_builtin(tokens);
        free_tokens(tokens);
        return ret;
    }
    
    // Split into commands by pipe
    int max_cmds = 16;
    char ***commands = malloc(sizeof(char**) * max_cmds);
    int ncmds = 0;
    
    int arg_start = 0;
    for (int i = 0; i < ntokens; ++i) {
        if (strcmp(tokens[i], "|") == 0) {
            free(tokens[i]);
            tokens[i] = NULL; 
            commands[ncmds++] = &tokens[arg_start];
            arg_start = i + 1;
        }
    }
    commands[ncmds++] = &tokens[arg_start];
    
    launch_pipeline(commands, ncmds, background, line);
    
    free(commands);
    // Note: individual token strings are freed in main loop or better management needed
    // Here we simplified memory management for clarity. 
    // Ideally we deep copy into job or free after wait.
    // Given we might default to job control for FG, we depend on job cleaning up cmdline.
    free_tokens(tokens); 
    return 0;
}

// Signal handlers
void sigint_handler(int signo) {
    if (signo == SIGINT) {
        printf("\n");
        // Re-print prompt handled by main loop refreshing or just ignore
    }
}

void sigtstp_handler(int signo) {
    // Forwarded to FG group automatically by terminal driver usually,
    // but shell ignores it so it doesn't stop itself.
}

void sigchld_handler(int signo) {
    // Easiest is to harvest zombies in the main loop or here.
    // Async harvesting can be race-prone with global "jobs".
    // We'll rely on explicit polling in remove_done_jobs in main loop
    // But we need to handle background jobs finishing asynchronously
    int status;
    pid_t pid;
    while ((pid = waitpid(-1, &status, WNOHANG | WUNTRACED)) > 0) {
        if (WIFEXITED(status) || WIFSIGNALED(status)) {
            job_t *j = find_job_by_pgid(pid); // This assumes pgid == pid leader
            if (j) j->state = DONE;
        } else if (WIFSTOPPED(status)) {
             job_t *j = find_job_by_pgid(pid);
            if (j) j->state = STOPPED;
        }
    }
}
