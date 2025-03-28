#! /usr/bin/perl
################################################################################
##
## Copyright 2006 - 2017, Paul Beckingham, Federico Hernandez.
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included
## in all copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
## OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
## THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.
##
## http://www.opensource.org/licenses/mit-license.php
##
################################################################################

#!/usr/bin/perl
use strict;
use warnings;
use Time::Local;

# Priority mappings
my %priority_map = (
  'a' => 'H', 'b' => 'M', 'c' => 'L', 'd' => 'L', 'e' => 'L', 'f' => 'L',
  'g' => 'L', 'h' => 'L', 'i' => 'L', 'j' => 'L', 'k' => 'L', 'l' => 'L',
  'm' => 'L', 'n' => 'L', 'o' => 'L', 'p' => 'L', 'q' => 'L', 'r' => 'L',
  's' => 'L', 't' => 'L', 'u' => 'L', 'v' => 'L', 'w' => 'L', 'x' => 'L',
  'y' => 'L', 'z' => 'L');

# Proper JSON escaping function
sub json_escape {
    my ($string) = @_;
    
    # Escape special characters
    $string =~ s/\\/\\\\/g;  # Backslash
    $string =~ s/"/\\"/g;    # Double quote
    $string =~ s/\n/\\n/g;   # Newline
    $string =~ s/\r/\\r/g;   # Carriage return
    $string =~ s/\t/\\t/g;   # Tab
    $string =~ s/\f/\\f/g;   # Form feed
    $string =~ s/\b/\\b/g;   # Backspace
    
    return $string;
}

my @tasks;
while (my $todo = <>)
{
  chomp $todo; # Remove newline
  next if $todo =~ /^\s*$/;  # Skip empty lines
  
  my $status = 'pending';
  my $priority = '';
  my $entry = '';
  my $end = '';
  my @projects;
  my @contexts;
  my $description = '';
  my $due = '';

  # pending + pri + entry
  if ($todo =~ /^\(([A-Z])\)\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $priority, $entry, $description) = ('pending', $1, epoch ($2), $3);
  }

  # pending + pri
  elsif ($todo =~ /^\(([A-Z])\)\s(.+)$/i)
  {
    ($status, $priority, $description) = ('pending', $1, $2);
  }

  # pending + entry
  elsif ($todo =~ /^(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $entry, $description) = ('pending', epoch ($1), $2);
  }

  # done + end + entry
  elsif ($todo =~ /^x\s(\d{4}-\d{2}-\d{2})\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $end, $entry, $description) = ('completed', epoch ($1), epoch ($2), $3);
  }

  # done + end
  elsif ($todo =~ /^x\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $end, $description) = ('completed', epoch ($1), $2);
  }

  # done
  elsif ($todo =~ /^x\s(.+)$/i)
  {
    ($status, $description) = ('completed', $1);
  }

  # pending
  elsif ($todo =~ /^(.+)$/i)
  {
    ($status, $description) = ('pending', $1);
  }

  # Project
  @projects = $description =~ /\+(\S+)/ig;

  # Contexts
  @contexts = $description =~ /\@(\S+)/ig;

  # Due
  $due = epoch ($1) if $todo =~ /\sdue:(\d{4}-\d{2}-\d{2})/i;

  # Map priorities
  $priority = $priority_map{lc $priority} if $priority ne '';

  # Pick first project
  my $first_project = shift @projects;

  # Escape all string values
  $description = json_escape($description);
  $first_project = json_escape($first_project) if defined $first_project;
  @contexts = map { json_escape($_) } @contexts;

  # Compose the JSON object
  my $json = '';
  $json .= "{\"status\":\"${status}\"";
  $json .= ",\"priority\":\"${priority}\""     if defined $priority && $priority ne '';
  $json .= ",\"project\":\"${first_project}\"" if defined $first_project && $first_project ne '';
  $json .= ",\"entry\":\"${entry}\""           if $entry ne '';
  $json .= ",\"end\":\"${end}\""               if $end ne '';
  $json .= ",\"due\":\"${due}\""               if $due ne '';

  if (@contexts)
  {
    $json .= ",\"tags\":[" . join (',', map {"\"$_\""} @contexts) . "]";
  }

  $json .= ",\"description\":\"${description}\"}";

  push @tasks, $json;
}

# Output json with commas between elements
print "[\n", join (",\n", @tasks), "\n]\n";
exit 0;

################################################################################
sub epoch
{
  my ($input) = @_;

  my ($y, $m, $d) = $input =~ /(\d{4})-(\d{2})-(\d{2})/;
  return timelocal (0, 0, 0, $d, $m-1, $y-1900);
}

################################################################################