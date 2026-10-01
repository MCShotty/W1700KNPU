#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
 if (argc != 2) return 2;
 int (*calls)(void)=dlsym(RTLD_DEFAULT,"real_chown_probe_calls");
 if (!calls) return 3;
 errno=0;
 int result=fchownat(AT_FDCWD,argv[1],123,456,AT_SYMLINK_NOFOLLOW), error=errno;
 struct stat st;
 if (fstatat(AT_FDCWD,argv[1],&st,AT_SYMLINK_NOFOLLOW)) return 4;
 printf("{\"result\":%d,\"errno\":%d,\"simulated_uid\":%u,\"simulated_gid\":%u,\"real_call_attempts\":%d}\n",result,error,(unsigned)st.st_uid,(unsigned)st.st_gid,calls());
 return 0;
}
